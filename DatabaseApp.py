import streamlit as st
import streamlit_nested_layout
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

def modify_column_type(db_name, table_name, column_name, new_type):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Get the existing schema
    print("get schema")
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()

    # Build new table schema dynamically
    print("building new table")
    new_table_name = f"{table_name}_new"
    column_defs = []
    for col in columns:
        col_name, col_type = col[1], col[2]
        col_type = new_type if col_name == column_name else col_type
        column_defs.append(f"{col_name} {col_type}")

    column_defs_str = ", ".join(column_defs)
    cursor.execute(f"CREATE TABLE {new_table_name} ({column_defs_str})")

    # Copy data over, casting column if needed
    print("copying")
    column_names = ", ".join([col[1] for col in columns])
    cast_exprs = ", ".join([f"CAST({col_name} AS {new_type})" if col_name == column_name else col_name for col_name in column_names.split(", ")])
    
    print("insert")
    cursor.execute(f"INSERT INTO {new_table_name} ({column_names}) SELECT {cast_exprs} FROM {table_name}")

    # Drop the old table
    cursor.execute(f"DROP TABLE {table_name}")

    # Rename the new table
    cursor.execute(f"ALTER TABLE {new_table_name} RENAME TO {table_name}")

    conn.commit()
    conn.close()

# App title and styling
st.title("CSV Database Manager")
st.write("Upload CSV files, manage your database, and run queries easily")

# Initialize session state for tracking database operations
if 'current_query_result' not in st.session_state:
    st.session_state.current_query_result = None

# Database selection with dropdown
st.subheader("1. Select or Create Database")
db_list = get_databases()

# Create search box
search_term = st.text_input("Search databases:")

# Filter options based on search
if search_term:
    filtered_options = [option for option in db_list 
                      if search_term.lower() in option.lower()]
else:
    filtered_options = db_list
# Show filtered dropdown
if filtered_options:
    selected_db = st.selectbox("Select Databases:", filtered_options)
else:
    st.warning("No matches found")
    selected_db = st.selectbox("Select Databases:", db_list)

if selected_db:
    st.success(f"Using database: {selected_db}")
    
    # CSV Import Section
    st.subheader("2. Import CSV Data")
    
    uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=["csv","xlsx"])
        
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
        #EXCEL  =  application/vnd.openxmlformats-officedocument.spreadsheetml.sheet 
        #CSV  =  text/csv 
        #print(uploaded_file)

        if(uploaded_file.type == "text/csv"):
            # Read CSV
            df = pd.read_csv(uploaded_file)
        elif (uploaded_file.type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"):
            read_file = pd.read_excel(uploaded_file)

            read_file.to_csv(uploaded_file.name+".csv",  
                  index=False, 
                  header=True,
                  sep=",")
            # read csv file
            df = pd.read_csv(uploaded_file.name+".csv")

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

    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = False

    if st.button("Refresh Database Info"):
        tables = get_tables(selected_db)

    if tables:
        # Initialize session state for each dynamically generated widget
        for widget in tables:
            widget = widget.strip()  # Clean up whitespace
            if widget:
                confirm_key = f"confirm_{widget}"  # Unique session key
                if confirm_key not in st.session_state:
                    st.session_state[confirm_key] = False

        tables_expander = st.expander(f"Tables in database ({len(tables)}):")
        with tables_expander:
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
                    
                    # Modify column data type
                    table_columns = []
                    for col in columns:
                        table_columns.append(col[1])
                    column_to_change = st.selectbox("Select column to modify:", table_columns, key=f"modify_column_select_{table}")
                    data_types = {"BOOLEAN":"BOOLEAN", "NUMBER":"FLOAT(30,4)", "TEXT":"TEXT(10000)"}

                    selected_type = st.selectbox("Select new data type:", list(data_types.keys()), key=f"data_type_select_{table}")

                    # Apply conversion if button is clicked
                    if st.button("Convert Column", key=f"convert_{table}"):
                        try:
                            modify_column_type(selected_db,table,column_to_change,selected_type)
                            st.success(f"Column '{column_to_change}' converted to {selected_type}!")
                        except Exception as e:
                            st.error(f"Error: {e}")

                    # Show sample data
                    sample = pd.read_sql_query(f"SELECT * FROM {table} LIMIT 5", conn)
                    st.write("Sample data:")
                    st.dataframe(sample)
                    
                    # Delete button to drop a table
                    if st.button(f"Delete {table}", key=f"delete_{table}"):
                        st.session_state[f"confirm_{table}"] = True  # Trigger confirmation

                    # Show confirmation prompt if delete was clicked
                    if st.session_state[f"confirm_{table}"]:
                        st.warning(f"Are you sure you want to delete {table}?")
                        col1, col2 = st.columns(2)

                        # Confirm deletion
                        with col1:
                            if st.button(f"Yes, Delete {table}", key=f"yes_{table}"):
                                cursor.execute(f"DROP TABLE {table};")
                                st.success(f"{table} deleted!")
                                st.session_state[f"confirm_{table}"] = False  # Reset state

                        # Cancel deletion
                        with col2:
                            if st.button(f"Cancel {table}", key=f"cancel_{table}_2"):
                                st.session_state[f"confirm_{table}"] = False  # Reset state
                                st.info(f"Deletion canceled for {table}.")
                    
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
                                min_value=0, 
                                max_value=min(num_rows, 500),  # Cap at 500 for performance
                                value=min(num_rows, 50))  # Default to 50 rows
        
        # Show the data
        st.dataframe(st.session_state.current_query_result.head(display_rows))
        
        # Show row count
        st.write(f"Showing {display_rows} of {num_rows} rows")
else:
    st.info("Please select or create a database to continue.")