import os
import requests
import pymysql
import pandas as pd
from datetime import datetime, timedelta


def get_base_url():
    today = datetime.now()
    previous_month = today.replace(day=1) - timedelta(days=1)
    previous_month_year = previous_month.strftime("%Y")
    previous_month_name = previous_month.strftime("%b").lower()
    return f'https://portal.amfiindia.com/spages/am{previous_month_name}{previous_month_year}repo.xls'
  

def download_previous_month_report(folder_path):
    try:
        base_url = get_base_url()
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        file_path = os.path.join(folder_path, os.path.basename(base_url))

        with requests.get(base_url) as req:
            if req.status_code == 200:
                with open(file_path, 'wb') as f:
                    for chunk in req.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                return file_path
            else:
                print(f"Failed to download: HTTP status code {req.status_code}")
                return None
    except Exception as e:
        print(f"An error occurred during download: {e}")
        return None

def process_report(file_path):
    try:
        df = pd.read_excel(file_path, skiprows=1)


        new_header_names = ['SR', 'Scheme Name', 'No of Scheme', 'No of Folio', 'Gross Sales', 'Redemption', 'Net Sales', 'AUM', 'AAUM', 'No of Portfolio', 'NAV']
        df.columns = new_header_names

        df['SR'] = df['SR'].astype(str)

        # Define scheme type mappings
        scheme_type_map = {'A': 'Open Ended Scheme', 'B': 'Closed Ended Scheme', 'C': 'Interval Scheme'}
        detailed_scheme_map = {
            'I': 'Income/Debt Oriented Schemes',
            'II': 'Growth/Equity Oriented Schemes',
            'III': 'Hybrid Schemes',
            'IV': 'Solution Oriented Schemes',
            'V': 'Other Schemes'
        }


        current_scheme = None
        current_detailed_scheme = None


        def get_scheme_type(x):
            nonlocal current_scheme
            if x in scheme_type_map:
                current_scheme = scheme_type_map[x]
            return current_scheme

        def get_detailed_scheme(x):
            nonlocal current_detailed_scheme
            if x in detailed_scheme_map:
                current_detailed_scheme = detailed_scheme_map[x]
            return current_detailed_scheme


        df['Scheme Type'] = df['SR'].apply(get_scheme_type)
        df['Detailed Scheme Type'] = df['SR'].apply(get_detailed_scheme)


        df['Scheme Type'] = df['Scheme Type'].ffill()
        df['Detailed Scheme Type'] = df['Detailed Scheme Type'].ffill()


        df = df.dropna(thresh=7)


        def filter_scheme_names(df):
            unwanted_strings = ['Sub Total', 'Total', 'Grand Total', 'Fund of Funds Scheme (Domestic) **']
            filtered_df = df[~df['Scheme Name'].astype(str).apply(lambda x: any(substring in x for substring in unwanted_strings))]
            return filtered_df

        df = filter_scheme_names(df)


        df = df.iloc[1:]

        return df
    except Exception as e:
        print(f"An error occurred during processing: {e}")
        return None

def test_mysql_connection(host, user, password, database):
    try:
        connection = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=3306
        )
        if connection.open:
            print("Successfully connected to MySQL database!")
            connection.close()
            return True
    except pymysql.MySQLError as e:
        print(f"Error: {e}")
        return False

def create_mysql_table(host, user, password, database):
    connection = None
    try:
        connection = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=3306
        )
        if connection.open:
            cursor = connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS amfi_reports (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    SR VARCHAR(255),
                    Scheme_Name VARCHAR(255),
                    No_of_Scheme INT,
                    No_of_Folio INT,
                    Gross_Sales DECIMAL(15, 2),
                    Redemption DECIMAL(15, 2),
                    Net_Sales DECIMAL(15, 2),
                    AUM DECIMAL(15, 2),
                    AAUM DECIMAL(15, 2),
                    No_of_Portfolio INT,
                    NAV DECIMAL(15, 2),
                    Scheme_Type VARCHAR(255),
                    Detailed_Scheme_Type VARCHAR(255)
                )
            """)
            print("Table created successfully")
    except pymysql.MySQLError as e:
        print(f"Error: {e}")
    finally:
        if connection and connection.open:
            cursor.close()
            connection.close()

def upload_to_mysql(host, user, password, database, df):
    connection = None
    try:
        connection = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=3306
        )
        if connection.open:
            cursor = connection.cursor()
            for _, row in df.iterrows():
                sql ="""
                    INSERT INTO amfi_reports (
                        SR, Scheme_Name, No_of_Scheme, No_of_Folio, Gross_Sales, Redemption, Net_Sales, AUM, AAUM, No_of_Portfolio, NAV, Scheme_Type, Detailed_Scheme_Type
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                      """
                values = (
                    row['SR'], row['Scheme Name'], row['No of Scheme'], row['No of Folio'], row['Gross Sales'], row['Redemption'], row['Net Sales'], row['AUM'], row['AAUM'], row['No of Portfolio'], row['NAV'], row['Scheme Type'], row['Detailed Scheme Type']
                )
                cursor.execute(sql, values)
            connection.commit()
            print("Data uploaded successfully")
    except pymysql.MySQLError as e:
        print(f"Error: {e}")
    finally:
        if connection and connection.open:
            cursor.close()
            connection.close()


folder_path = r'D:\tableau'


host = 'localhost'
user = 'root'
password = 'Anusha@9525'
database = 'stat_amfi_project'


if test_mysql_connection(host, user, password, database):

    create_mysql_table(host, user, password, database)

    downloaded_file = download_previous_month_report(folder_path)
    if downloaded_file:

        transformed_df = process_report(downloaded_file)
        if transformed_df is not None:

            upload_to_mysql(host, user, password, database, transformed_df)
else:
    print("Failed to connect to MySQL. Please check your connection details and ensure MySQL is running.")
