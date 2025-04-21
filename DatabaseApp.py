import streamlit as st
import pandas as pd
import sqlite3
import os
import glob
from datetime import datetime

# Set page configuration
st.set_page_config(page_title="CSV Database Manager", layout="wide")

# Function to get list of databases in current directory
def get_databases():
    db_files = glob.glob("*.db")
    return ["Create new database..."] + db_files

# Function to get list of tables in a database
def get_tables(db_path):
    if not os.path.exists(db_path):
        return []
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    conn.close()
    
    return [table[0] for table in tables]

# Database connection helper
def get_connection(db_path):
    return sqlite3.connect(db_path)

# App title and styling
st.title("CSV Database Manager")
st.write("Upload CSV files, manage your database, and run queries easily")

# Initialize session state for tracking database operations
if 'current_query_result' not in st.session_state:
    st.session_state.current_query_result = None

# Database selection with dropdown
st.subheader("1. Select or Create Database")
db_list = get_databases()
selected_db = st.selectbox("Choose a database:", db_list)

# Handle new database creation
if selected_db == "Create new database...":
    new_db_name = st.text_input("Enter new database name (without .db extension):")
    if new_db_name:
        selected_db = f"{new_db_name}.db"

if selected_db:
    st.success(f"Using database: {selected_db}")
    
    # CSV Import Section
    st.subheader("2. Import CSV Data")
    
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
    
    # Table selection/creation
    tables = get_tables(selected_db)
    table_options = ["Create new table..."] + tables
    
    selected_table = st.selectbox("Choose a table:", table_options)
    
    if selected_table == "Create new table...":
        new_table_name = st.text_input("Enter new table name:")
        if new_table_name:
            selected_table = new_table_name
    
    # Import mode selection
    if selected_table in tables:
        import_mode = st.radio(
            "Import mode:",
            ["Append to existing table", "Replace existing table"]
        )
        if_exists = "append" if import_mode == "Append to existing table" else "replace"
    else:
        if_exists = "replace"  # For new tables
    
    if uploaded_file and selected_table and st.button("Import CSV to Database"):
        # Read CSV
        df = pd.read_csv(uploaded_file)
        
        # Display preview
        st.write("Preview of imported data:")
        st.dataframe(df.head())
        
        # Save to database
        try:
            conn = get_connection(selected_db)
            df.to_sql(selected_table, conn, if_exists=if_exists, index=False)
            conn.close()
            
            st.success(f"Data imported to table '{selected_table}' successfully!")
        except Exception as e:
            st.error(f"Error importing data: {e}")
    
    # Database Info Section
    st.subheader("3. Database Information")
    
    if st.button("Refresh Database Info"):
        tables = get_tables(selected_db)
        
    if tables:
        st.write(f"Tables in database ({len(tables)}):")
        for table in tables:
            expander = st.expander(f"Table: {table}")
            with expander:
                conn = get_connection(selected_db)
                # Get column info
                cursor = conn.cursor()
                cursor.execute(f"PRAGMA table_info({table});")
                columns = cursor.fetchall()
                
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                row_count = cursor.fetchone()[0]
                
                # Display table info
                st.write(f"Rows: {row_count}")
                st.write("Columns:")
                col_df = pd.read_sql_query(f"PRAGMA table_info({table});", conn)
                st.dataframe(col_df[['name', 'type']])
                
                # Show sample data
                sample = pd.read_sql_query(f"SELECT * FROM {table} LIMIT 5", conn)
                st.write("Sample data:")
                st.dataframe(sample)
                
                conn.close()
    else:
        st.info("No tables found in the selected database.")
    
    # Query Section
    st.subheader("4. Run SQL Queries")
    
    # Helper text for SQL queries
    with st.expander("SQL Query Help"):
        st.markdown("""
        ### Basic SQL Query Examples:
        - **View all data**: `SELECT * FROM table_name`
        - **Filter data**: `SELECT * FROM table_name WHERE column_name = 'value'`
        - **Sort data**: `SELECT * FROM table_name ORDER BY column_name DESC`
        - **Group data**: `SELECT column_name, COUNT(*) FROM table_name GROUP BY column_name`
        - **Join tables**: `SELECT t1.column, t2.column FROM table1 t1 JOIN table2 t2 ON t1.id = t2.id`
        """)
    
    query = st.text_area("Enter your SQL query:", height=100)
    
    col1, col2 = st.columns(2)
    with col1:
        if query and st.button("Run Query"):
            try:
                conn = get_connection(selected_db)
                results = pd.read_sql_query(query, conn)
                conn.close()
                
                st.session_state.current_query_result = results
                
                st.write("Query Results:")
                st.dataframe(results)
                
            except Exception as e:
                st.error(f"Error executing query: {e}")
    
    with col2:
        if st.session_state.current_query_result is not None and not st.session_state.current_query_result.empty:
            if st.button("Export Results to CSV"):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"query_result_{timestamp}.csv"
                st.session_state.current_query_result.to_csv(filename, index=False)
                
                # Create a download link for the CSV file
                with open(filename, "rb") as f:
                    csv_bytes = f.read()
                
                st.download_button(
                    label="Download CSV File",
                    data=csv_bytes,
                    file_name=filename,
                    mime="text/csv",
                )
                
                st.success(f"Results exported to {filename}")
    
    # Simple Data Display Section
    if st.session_state.current_query_result is not None and not st.session_state.current_query_result.empty:
        st.subheader("5. Data View")
        
        # Display the full query result as a table
        st.write("Query Results as Table:")
        
        # Get the number of rows in the result
        num_rows = len(st.session_state.current_query_result)
        
        # Allow user to control how many rows to display
        display_rows = st.slider("Number of rows to display:", 
                                min_value=1, 
                                max_value=min(num_rows, 500),  # Cap at 500 for performance
                                value=min(num_rows, 50))  # Default to 50 rows
        
        # Show the data
        st.dataframe(st.session_state.current_query_result.head(display_rows))
        
        # Show row count
        st.write(f"Showing {display_rows} of {num_rows} rows")
else:
    st.info("Please select or create a database to continue.")