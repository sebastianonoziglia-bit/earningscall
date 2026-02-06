import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import plotly.graph_objects as go
from datetime import datetime
import logging
import json
import re
from io import StringIO

# Page config must be the first Streamlit command
st.set_page_config(page_title="SQL Manager", page_icon="🔧", layout="wide")

# Apply shared page styles
from utils.styles import get_page_style
st.markdown(get_page_style(), unsafe_allow_html=True)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_connection():
    """Get a database connection"""
    return psycopg2.connect(
        dbname=os.getenv('PGDATABASE'),
        user=os.getenv('PGUSER'),
        password=os.getenv('PGPASSWORD'),
        host=os.getenv('PGHOST'),
        port=os.getenv('PGPORT')
    )

def execute_query(query):
    """Execute a SQL query and return results as a DataFrame"""
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query)
        
        # Get column names from cursor description
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        
        # Fetch all rows and convert to DataFrame
        results = cursor.fetchall()
        df = pd.DataFrame(results)
        
        cursor.close()
        conn.close()
        
        return df
    except Exception as e:
        st.error(f"Error executing query: {str(e)}")
        return pd.DataFrame()

def get_schema():
    """Get database schema information as DataFrame"""
    query = """
    SELECT 
        t.table_name, 
        c.column_name, 
        c.data_type, 
        c.column_default,
        c.is_nullable
    FROM 
        information_schema.tables t
    JOIN 
        information_schema.columns c 
    ON 
        t.table_name = c.table_name
    WHERE 
        t.table_schema = 'public'
    ORDER BY 
        t.table_name, 
        c.ordinal_position;
    """
    return execute_query(query)

def get_table_sample(table_name, limit=10):
    """Get a sample of data from a specific table"""
    query = f"SELECT * FROM {table_name} LIMIT {limit}"
    return execute_query(query)

# Password protection
def check_password():
    """Check if the user has entered the correct password"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.title("🔒 SQL Manager Access")
        st.write("This page contains powerful database management tools. Please enter the access password:")
        
        password = st.text_input("Password:", type="password", key="sql_manager_password")
        
        if st.button("Login"):
            # You can change this password as needed
            if password == "Company123!":
                st.session_state.authenticated = True
                st.success("Access granted! Refreshing page...")
                st.rerun()
            else:
                st.error("Incorrect password. Please try again.")
        
        return False
    
    return True

# Check authentication first
if not check_password():
    st.stop()

# Main UI (only shown if authenticated)
st.title("SQL Manager 🔧")
st.write("Advanced database management and query tools for financial data.")

# Add logout button
col1, col2 = st.columns([1, 6])
with col1:
    if st.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.rerun()

def execute_update_query(query, commit=True):
    """Execute a SQL query that modifies data (INSERT, UPDATE, DELETE)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        
        if commit:
            conn.commit()
            
        rows_affected = cursor.rowcount
        cursor.close()
        conn.close()
        
        return rows_affected
    except Exception as e:
        st.error(f"Error executing update query: {str(e)}")
        return 0

def get_table_columns(table_name):
    """Get column information for a specific table"""
    query = f"""
    SELECT 
        column_name, 
        data_type, 
        is_nullable,
        column_default,
        ordinal_position
    FROM 
        information_schema.columns
    WHERE 
        table_name = '{table_name}'
        AND table_schema = 'public'
    ORDER BY 
        ordinal_position;
    """
    return execute_query(query)

def get_primary_keys(table_name):
    """Get primary key columns for a table"""
    query = f"""
    SELECT
        kcu.column_name
    FROM
        information_schema.table_constraints tc
    JOIN
        information_schema.key_column_usage kcu
    ON
        tc.constraint_name = kcu.constraint_name
    WHERE
        tc.table_name = '{table_name}'
        AND tc.constraint_type = 'PRIMARY KEY'
        AND tc.table_schema = 'public'
    ORDER BY
        kcu.ordinal_position;
    """
    result = execute_query(query)
    if not result.empty:
        return result['column_name'].tolist()
    return []

def get_create_table_sql(table_name):
    """Generate CREATE TABLE SQL for a given table"""
    columns_df = get_table_columns(table_name)
    primary_keys = get_primary_keys(table_name)
    
    if columns_df.empty:
        return ""
    
    sql = f"CREATE TABLE {table_name} (\n"
    
    # Add columns
    for _, row in columns_df.iterrows():
        column = row['column_name']
        data_type = row['data_type']
        nullable = "NULL" if row['is_nullable'] == 'YES' else "NOT NULL"
        default = f"DEFAULT {row['column_default']}" if pd.notna(row['column_default']) else ""
        
        sql += f"    {column} {data_type} {nullable} {default},\n"
    
    # Add primary key if exists
    if primary_keys:
        sql += f"    PRIMARY KEY ({', '.join(primary_keys)})\n"
    else:
        # Remove trailing comma
        sql = sql.rstrip(",\n") + "\n"
    
    sql += ");"
    return sql

def generate_insert_statement(table_name, data_df):
    """Generate INSERT SQL statements for a dataframe"""
    if data_df.empty:
        return ""
    
    # Get column names
    columns = data_df.columns.tolist()
    columns_str = ", ".join(columns)
    
    # Generate individual INSERT statements for each row
    statements = []
    
    for _, row in data_df.iterrows():
        # Format values based on type
        values = []
        for col in columns:
            val = row[col]
            
            if pd.isna(val):
                values.append("NULL")
            elif isinstance(val, (int, float)):
                values.append(str(val))
            elif isinstance(val, bool):
                values.append("TRUE" if val else "FALSE")
            else:
                # Escape single quotes for string values
                val_str = str(val).replace("'", "''")
                values.append(f"'{val_str}'")
        
        values_str = ", ".join(values)
        statements.append(f"INSERT INTO {table_name} ({columns_str}) VALUES ({values_str});")
    
    return "\n".join(statements)

def create_text_editor(default_text="", height=300, key=None):
    """Create a code editor with line numbers"""
    # Create custom CSS for code editor with line numbers
    st.markdown("""
    <style>
    .line-numbers {
        font-family: monospace;
        background-color: #f5f5f5;
        padding: 10px;
        border-radius: 5px;
        display: flex;
    }
    .line-numbers-rows {
        width: 30px;
        color: #999;
        text-align: right;
        padding-right: 8px;
        border-right: 1px solid #ddd;
        user-select: none;
    }
    .editor-area {
        flex-grow: 1;
        margin-left: 8px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Line numbers calculation
    if default_text:
        lines = default_text.count('\n') + 1
        line_numbers = '\n'.join([f"{i}." for i in range(1, lines + 10)])
    else:
        line_numbers = "1."
    
    # Create a two-column layout
    col1, col2 = st.columns([1, 20])
    
    with col1:
        st.markdown(f"<div class='line-numbers-rows'>{line_numbers}</div>", unsafe_allow_html=True)
    
    with col2:
        text_area = st.text_area("", value=default_text, height=height, key=key, label_visibility="collapsed")
    
    return text_area

tabs = st.tabs(["Database Editor", "Schema Explorer", "M2 Money Supply Data", "SQL Workbench", "Full Database Export"])

with tabs[0]:
    st.header("Database Editor")
    st.write("Here you can edit data in the database tables.")
    
    schema_df = get_schema()
    
    if not schema_df.empty:
        # Get list of tables
        tables = schema_df['table_name'].unique()
        
        # Table selection
        selected_table = st.selectbox("Select a table to edit:", tables)
        
        if selected_table:
            # Create tabs for different operations
            crud_tabs = st.tabs(["View & Edit", "Create", "Delete", "Import/Export"])
            
            with crud_tabs[0]:
                st.subheader(f"View & Edit Table: {selected_table}")
                
                # Get primary key columns
                primary_keys = get_primary_keys(selected_table)
                primary_key_str = ", ".join(primary_keys) if primary_keys else "No primary key"
                st.write(f"Primary Key: {primary_key_str}")
                
                # Limit control
                limit = st.slider("Number of rows to display:", min_value=10, max_value=1000, value=100, step=10)
                
                # Order by controls
                columns_df = get_table_columns(selected_table)
                if not columns_df.empty:
                    column_list = columns_df['column_name'].tolist()
                    sort_column = st.selectbox("Sort by column:", column_list)
                    sort_direction = st.radio("Sort direction:", ["ASC", "DESC"], horizontal=True)
                    
                    # Build query with order by
                    query = f"SELECT * FROM {selected_table} ORDER BY {sort_column} {sort_direction} LIMIT {limit}"
                    data_df = execute_query(query)
                    
                    if not data_df.empty:
                        # Display data with edit buttons
                        st.dataframe(data_df)
                        
                        # Edit functionality
                        st.subheader("Edit Row")
                        
                        if primary_keys:
                            # Select a row to edit by primary key
                            row_selector = {}
                            for pk in primary_keys:
                                pk_values = data_df[pk].unique()
                                row_selector[pk] = st.selectbox(f"Select {pk}:", pk_values)
                            
                            # Build WHERE clause for primary key
                            where_clause = " AND ".join([f"{pk} = '{row_selector[pk]}'" for pk in primary_keys])
                            
                            # Get the selected row
                            selected_row = data_df[data_df[primary_keys[0]] == row_selector[primary_keys[0]]]
                            for i in range(1, len(primary_keys)):
                                selected_row = selected_row[selected_row[primary_keys[i]] == row_selector[primary_keys[i]]]
                            
                            if not selected_row.empty:
                                st.write("Edit row values:")
                                
                                # Create input fields for each column
                                new_values = {}
                                for col in data_df.columns:
                                    current_value = selected_row[col].iloc[0]
                                    
                                    # Different input types based on data type
                                    if pd.isna(current_value):
                                        current_value = ""
                                    
                                    # Disable editing for primary keys
                                    disabled = col in primary_keys
                                    
                                    if isinstance(current_value, (int, float)):
                                        new_values[col] = st.number_input(f"{col}:", value=float(current_value), disabled=disabled)
                                    elif isinstance(current_value, bool):
                                        new_values[col] = st.checkbox(f"{col}:", value=current_value, disabled=disabled)
                                    else:
                                        new_values[col] = st.text_input(f"{col}:", value=str(current_value), disabled=disabled)
                                
                                # Update button
                                if st.button("Update Row"):
                                    # Build SET clause
                                    set_clause_parts = []
                                    for col, value in new_values.items():
                                        if col not in primary_keys:  # Skip primary keys in SET clause
                                            if pd.isna(value) or value == "":
                                                set_clause_parts.append(f"{col} = NULL")
                                            elif isinstance(value, (int, float)):
                                                set_clause_parts.append(f"{col} = {value}")
                                            elif isinstance(value, bool):
                                                set_clause_parts.append(f"{col} = {str(value).upper()}")
                                            else:
                                                # Escape single quotes
                                                escaped_value = str(value).replace("'", "''")
                                                set_clause_parts.append(f"{col} = '{escaped_value}'")
                                    
                                    set_clause = ", ".join(set_clause_parts)
                                    
                                    # Create and execute UPDATE query
                                    update_query = f"UPDATE {selected_table} SET {set_clause} WHERE {where_clause}"
                                    rows_affected = execute_update_query(update_query)
                                    
                                    if rows_affected > 0:
                                        st.success(f"Updated {rows_affected} row(s)")
                                    else:
                                        st.error("Failed to update row")
                            else:
                                st.warning("No row selected")
                        else:
                            st.warning("Table has no primary key. Cannot edit rows without a unique identifier.")
                    else:
                        st.warning(f"No data available in table {selected_table}")
                else:
                    st.error(f"Failed to get column information for table {selected_table}")
            
            with crud_tabs[1]:
                st.subheader(f"Create New Row in: {selected_table}")
                
                # Get column information
                columns_df = get_table_columns(selected_table)
                
                if not columns_df.empty:
                    # Create input fields for each column
                    new_row = {}
                    for _, col_info in columns_df.iterrows():
                        col_name = col_info['column_name']
                        data_type = col_info['data_type']
                        
                        # Check if column has a default value
                        has_default = pd.notna(col_info['column_default'])
                        
                        # Add note if column has default value
                        label = f"{col_name} ({data_type})"
                        if has_default:
                            label += f" [has default: {col_info['column_default']}]"
                        
                        # Different input types based on data type
                        if "int" in data_type or "serial" in data_type:
                            new_row[col_name] = st.number_input(label, step=1)
                        elif "numeric" in data_type or "float" in data_type or "double" in data_type:
                            new_row[col_name] = st.number_input(label, format="%.5f")
                        elif data_type == "boolean":
                            new_row[col_name] = st.checkbox(label)
                        elif "date" in data_type:
                            new_row[col_name] = st.date_input(label)
                        elif "timestamp" in data_type:
                            date_val = st.date_input(f"{label} (date)")
                            time_val = st.time_input(f"{label} (time)")
                            new_row[col_name] = f"{date_val} {time_val}"
                        elif "text" in data_type:
                            new_row[col_name] = st.text_area(label)
                        else:
                            new_row[col_name] = st.text_input(label)
                        
                        # Add checkbox to set NULL for nullable columns
                        if col_info['is_nullable'] == 'YES':
                            is_null = st.checkbox(f"Set {col_name} to NULL")
                            if is_null:
                                new_row[col_name] = None
                    
                    # Insert button
                    if st.button("Insert New Row"):
                        # Build column and value lists
                        columns = []
                        values = []
                        
                        for col, value in new_row.items():
                            if value is not None:  # Skip NULL values for columns with defaults
                                columns.append(col)
                                
                                if value is None:
                                    values.append("NULL")
                                elif isinstance(value, (int, float)):
                                    values.append(str(value))
                                elif isinstance(value, bool):
                                    values.append("TRUE" if value else "FALSE")
                                else:
                                    # Escape single quotes
                                    escaped_value = str(value).replace("'", "''")
                                    values.append(f"'{escaped_value}'")
                        
                        # Create and execute INSERT query
                        insert_query = f"INSERT INTO {selected_table} ({', '.join(columns)}) VALUES ({', '.join(values)})"
                        
                        try:
                            rows_affected = execute_update_query(insert_query)
                            
                            if rows_affected > 0:
                                st.success(f"Inserted row successfully")
                            else:
                                st.error("Failed to insert row")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                else:
                    st.error(f"Failed to get column information for table {selected_table}")
            
            with crud_tabs[2]:
                st.subheader(f"Delete From: {selected_table}")
                
                # Get primary key columns
                primary_keys = get_primary_keys(selected_table)
                primary_key_str = ", ".join(primary_keys) if primary_keys else "No primary key"
                st.write(f"Primary Key: {primary_key_str}")
                
                # Create tabs for different deletion methods
                delete_tabs = st.tabs(["By Primary Key", "Custom WHERE Clause"])
                
                with delete_tabs[0]:
                    if primary_keys:
                        # Get sample data to show primary key values
                        sample_data = get_table_sample(selected_table, 100)
                        
                        if not sample_data.empty:
                            st.dataframe(sample_data)
                            
                            # Select a row to delete by primary key
                            row_selector = {}
                            for pk in primary_keys:
                                pk_values = sample_data[pk].unique()
                                row_selector[pk] = st.selectbox(f"Select {pk} to delete:", pk_values)
                            
                            # Build WHERE clause for primary key
                            where_clause = " AND ".join([f"{pk} = '{row_selector[pk]}'" for pk in primary_keys])
                            
                            # Preview the DELETE query
                            delete_query = f"DELETE FROM {selected_table} WHERE {where_clause}"
                            st.code(delete_query, language="sql")
                            
                            # Delete confirmation
                            delete_confirm = st.checkbox("I understand this action will delete data permanently")
                            
                            if st.button("Delete Row") and delete_confirm:
                                try:
                                    rows_affected = execute_update_query(delete_query)
                                    
                                    if rows_affected > 0:
                                        st.success(f"Deleted {rows_affected} row(s)")
                                    else:
                                        st.warning("No rows were deleted. The row may have already been removed.")
                                except Exception as e:
                                    st.error(f"Error: {str(e)}")
                        else:
                            st.warning(f"No data available in table {selected_table}")
                    else:
                        st.warning("Table has no primary key. Use custom WHERE clause to delete rows.")
                
                with delete_tabs[1]:
                    st.write("Write a custom WHERE clause to delete specific rows.")
                    
                    where_clause = st.text_area("WHERE clause (without the 'WHERE' keyword):", height=100)
                    
                    if where_clause:
                        # Preview the DELETE query
                        delete_query = f"DELETE FROM {selected_table} WHERE {where_clause}"
                        st.code(delete_query, language="sql")
                        
                        # Preview the affected rows
                        preview_query = f"SELECT * FROM {selected_table} WHERE {where_clause} LIMIT 100"
                        
                        try:
                            preview_results = execute_query(preview_query)
                            
                            if not preview_results.empty:
                                st.write(f"This will delete {len(preview_results)} row(s) (showing up to 100):")
                                st.dataframe(preview_results)
                            else:
                                st.warning("No rows match this WHERE clause")
                        except Exception as e:
                            st.error(f"Error in WHERE clause: {str(e)}")
                        
                        # Delete confirmation
                        delete_confirm = st.checkbox("I understand this action will delete data permanently", key="custom_delete")
                        
                        if st.button("Execute DELETE") and delete_confirm:
                            try:
                                rows_affected = execute_update_query(delete_query)
                                
                                if rows_affected > 0:
                                    st.success(f"Deleted {rows_affected} row(s)")
                                else:
                                    st.warning("No rows were deleted")
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                    else:
                        st.warning("Please enter a WHERE clause")
            
            with crud_tabs[3]:
                st.subheader(f"Import/Export for: {selected_table}")
                
                export_tabs = st.tabs(["Export Data", "Export Schema", "Import Data"])
                
                with export_tabs[0]:
                    st.write("Export table data to CSV or SQL INSERT statements")
                    
                    # Query options
                    limit = st.number_input("Export row limit (0 for all rows):", min_value=0, value=1000)
                    
                    where_clause = st.text_input("Optional WHERE clause (without 'WHERE'):")
                    
                    # Format selection
                    export_format = st.radio("Export format:", ["CSV", "SQL INSERT"], horizontal=True)
                    
                    limit_clause = f"LIMIT {limit}" if limit > 0 else ""
                    where_statement = f"WHERE {where_clause}" if where_clause else ""
                    
                    query = f"SELECT * FROM {selected_table} {where_statement} {limit_clause}"
                    
                    if st.button("Generate Export"):
                        export_data = execute_query(query)
                        
                        if not export_data.empty:
                            if export_format == "CSV":
                                # Generate CSV
                                csv = export_data.to_csv(index=False)
                                
                                # Provide download link
                                st.download_button(
                                    label="Download CSV",
                                    data=csv,
                                    file_name=f"{selected_table}_export.csv",
                                    mime="text/csv"
                                )
                                
                                # Show preview
                                st.write("CSV Preview:")
                                st.code(csv[:1000] + ("..." if len(csv) > 1000 else ""), language="csv")
                            else:
                                # Generate SQL INSERT statements
                                inserts = generate_insert_statement(selected_table, export_data)
                                
                                # Provide download link
                                st.download_button(
                                    label="Download SQL",
                                    data=inserts,
                                    file_name=f"{selected_table}_inserts.sql",
                                    mime="text/plain"
                                )
                                
                                # Show preview
                                st.write("SQL INSERT Preview:")
                                st.code(inserts[:1000] + ("..." if len(inserts) > 1000 else ""), language="sql")
                        else:
                            st.warning(f"No data found in table {selected_table}")
                
                with export_tabs[1]:
                    st.write("Export table schema as CREATE TABLE statement")
                    
                    # Generate CREATE TABLE SQL
                    create_sql = get_create_table_sql(selected_table)
                    
                    if create_sql:
                        # Display the SQL
                        st.code(create_sql, language="sql")
                        
                        # Provide download button
                        st.download_button(
                            label="Download CREATE TABLE SQL",
                            data=create_sql,
                            file_name=f"{selected_table}_schema.sql",
                            mime="text/plain"
                        )
                    else:
                        st.warning(f"Failed to generate schema for table {selected_table}")
                
                with export_tabs[2]:
                    st.write("Import data from CSV or SQL")
                    
                    import_format = st.radio("Import format:", ["CSV", "SQL"], horizontal=True)
                    
                    if import_format == "CSV":
                        uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])
                        
                        if uploaded_file is not None:
                            try:
                                # Read CSV into dataframe
                                import_df = pd.read_csv(uploaded_file)
                                
                                # Display preview
                                st.write("Data Preview:")
                                st.dataframe(import_df.head(5))
                                
                                # Check columns match the table
                                table_columns = get_table_columns(selected_table)
                                table_col_list = set(table_columns['column_name'].tolist())
                                csv_col_list = set(import_df.columns.tolist())
                                
                                # Find missing or extra columns
                                missing_cols = table_col_list - csv_col_list
                                extra_cols = csv_col_list - table_col_list
                                
                                if missing_cols:
                                    st.warning(f"Missing columns in CSV: {', '.join(missing_cols)}")
                                
                                if extra_cols:
                                    st.warning(f"Extra columns in CSV that don't exist in table: {', '.join(extra_cols)}")
                                
                                # Import options
                                truncate_first = st.checkbox("Truncate table before import")
                                ignore_extra_cols = st.checkbox("Ignore extra columns")
                                
                                # Generate SQL preview
                                if st.button("Generate Import SQL"):
                                    # Filter dataframe if ignoring extra columns
                                    if ignore_extra_cols and extra_cols:
                                        valid_cols = list(csv_col_list - extra_cols)
                                        import_df = import_df[valid_cols]
                                    
                                    # Generate INSERT statements
                                    truncate_sql = f"TRUNCATE TABLE {selected_table};\n\n" if truncate_first else ""
                                    insert_sql = generate_insert_statement(selected_table, import_df)
                                    
                                    full_sql = truncate_sql + insert_sql
                                    
                                    # Show preview
                                    st.write(f"SQL Preview ({len(import_df)} rows):")
                                    st.code(full_sql[:1000] + ("..." if len(full_sql) > 1000 else ""), language="sql")
                                    
                                    # Create session state for the SQL
                                    st.session_state.import_sql = full_sql
                                    
                                    # Confirmation
                                    st.info(f"Ready to import {len(import_df)} rows. Click 'Execute Import' to proceed.")
                                
                                # Execute import button (only show if SQL has been generated)
                                if 'import_sql' in st.session_state:
                                    import_confirm = st.checkbox("I understand this will modify the database")
                                    
                                    if st.button("Execute Import") and import_confirm:
                                        try:
                                            # Split the SQL into individual statements
                                            statements = st.session_state.import_sql.split(';')
                                            
                                            # Execute each statement
                                            conn = get_connection()
                                            cursor = conn.cursor()
                                            
                                            success_count = 0
                                            total_count = 0
                                            
                                            for stmt in statements:
                                                if stmt.strip():
                                                    total_count += 1
                                                    try:
                                                        cursor.execute(stmt)
                                                        success_count += 1
                                                    except Exception as e:
                                                        st.error(f"Error executing statement: {e}")
                                                        st.code(stmt, language="sql")
                                            
                                            # Commit changes
                                            conn.commit()
                                            cursor.close()
                                            conn.close()
                                            
                                            st.success(f"Import completed: {success_count}/{total_count} statements executed successfully")
                                        except Exception as e:
                                            st.error(f"Import error: {e}")
                            except Exception as e:
                                st.error(f"Error processing CSV: {e}")
                    else:
                        # SQL import
                        sql_import = create_text_editor("-- Enter SQL statements here\n", height=200, key="sql_import")
                        
                        if st.button("Validate SQL"):
                            if not sql_import or sql_import.isspace():
                                st.warning("Please enter SQL statements")
                            else:
                                # Basic validation - just check for proper SQL keywords and table name
                                sql_lower = sql_import.lower()
                                
                                if "insert into" in sql_lower and selected_table.lower() in sql_lower:
                                    st.success("SQL validation passed")
                                    st.session_state.validated_sql = sql_import
                                else:
                                    st.warning(f"SQL should contain INSERT INTO statements for table {selected_table}")
                        
                        # Execute SQL button (only show if validation passed)
                        if 'validated_sql' in st.session_state:
                            import_confirm = st.checkbox("I understand this will modify the database", key="sql_import_confirm")
                            
                            if st.button("Execute SQL") and import_confirm:
                                try:
                                    # Split the SQL into individual statements
                                    statements = st.session_state.validated_sql.split(';')
                                    
                                    # Execute each statement
                                    conn = get_connection()
                                    cursor = conn.cursor()
                                    
                                    success_count = 0
                                    total_count = 0
                                    
                                    for stmt in statements:
                                        if stmt.strip():
                                            total_count += 1
                                            try:
                                                cursor.execute(stmt)
                                                success_count += 1
                                            except Exception as e:
                                                st.error(f"Error executing statement: {e}")
                                                st.code(stmt, language="sql")
                                    
                                    # Commit changes
                                    conn.commit()
                                    cursor.close()
                                    conn.close()
                                    
                                    st.success(f"Import completed: {success_count}/{total_count} statements executed successfully")
                                except Exception as e:
                                    st.error(f"Import error: {e}")
    else:
        st.warning("Failed to retrieve database schema")

with tabs[1]:
    st.header("Schema Explorer")
    st.write("Here you can explore the database schema to understand what tables and columns are available.")
    
    schema_df = get_schema()
    
    if not schema_df.empty:
        # Group by table name
        tables = schema_df['table_name'].unique()
        
        # Create expandable sections for each table
        for table in tables:
            with st.expander(f"Table: {table}"):
                table_schema = schema_df[schema_df['table_name'] == table].reset_index(drop=True)
                st.dataframe(table_schema[['column_name', 'data_type', 'is_nullable']])
                
                # Add a button to view sample data
                if st.button(f"View sample data from {table}"):
                    sample_df = get_table_sample(table)
                    if not sample_df.empty:
                        st.dataframe(sample_df)
                    else:
                        st.warning(f"No data available in table {table}")
    else:
        st.warning("Failed to retrieve database schema")

with tabs[1]:
    st.header("M2 Money Supply Data")
    st.write("Explore and visualize M2 money supply data from the database.")
    
    # Query options
    data_type = st.radio("Select data granularity:", ["Annual", "Monthly"])
    
    current_year = datetime.now().year
    year_range = st.slider("Select year range:", 
                         min_value=2010, 
                         max_value=current_year,
                         value=(2015, current_year))
    
    if data_type == "Annual":
        query = f"""
        SELECT year, value, annual_growth
        FROM m2_supply_annual
        WHERE year BETWEEN {year_range[0]} AND {year_range[1]}
        ORDER BY year
        """
    else:
        query = f"""
        SELECT date, value, monthly_growth, year, month
        FROM m2_supply_monthly
        WHERE year BETWEEN {year_range[0]} AND {year_range[1]}
        ORDER BY date
        """
    
    # Convert Decimal fields to float for Plotly compatibility
    try:
        m2_df = execute_query(query)
        if not m2_df.empty:
            for col in m2_df.columns:
                # Check if column contains Decimal objects
                if m2_df[col].dtype.name == 'object':
                    # Try to convert to float
                    try:
                        m2_df[col] = m2_df[col].astype(float)
                    except:
                        pass  # Keep as is if conversion fails
    except Exception as e:
        st.error(f"Error processing M2 data: {str(e)}")
        m2_df = pd.DataFrame()
    
    if not m2_df.empty:
        # Display the data
        st.dataframe(m2_df)
        
        # Create visualization
        fig = go.Figure()
        
        if data_type == "Annual":
            # Add bar chart for annual values
            fig.add_trace(go.Bar(
                x=m2_df['year'],
                y=m2_df['value'],
                name='M2 Supply (Billions USD)',
                marker_color='#1f77b4'
            ))
            
            # Add line chart for growth rate
            fig.add_trace(go.Scatter(
                x=m2_df['year'],
                y=m2_df['annual_growth'],
                name='Annual Growth Rate (%)',
                yaxis='y2',
                line=dict(color='#ff7f0e', width=3)
            ))
            
            # Set layout with dual Y-axes
            fig.update_layout(
                title='M2 Money Supply - Annual Data',
                xaxis=dict(title='Year'),
                yaxis=dict(
                    title='M2 Supply (Billions USD)',
                    titlefont=dict(color='#1f77b4'),
                    tickfont=dict(color='#1f77b4')
                ),
                yaxis2=dict(
                    title='Growth Rate (%)',
                    titlefont=dict(color='#ff7f0e'),
                    tickfont=dict(color='#ff7f0e'),
                    anchor='x',
                    overlaying='y',
                    side='right'
                ),
                legend=dict(x=0.01, y=0.99, orientation='h'),
                height=600
            )
            
        else:  # Monthly data
            # Add line chart for monthly values
            fig.add_trace(go.Scatter(
                x=m2_df['date'],
                y=m2_df['value'],
                name='M2 Supply (Billions USD)',
                line=dict(color='#1f77b4', width=2)
            ))
            
            # Add line chart for monthly growth rate
            fig.add_trace(go.Scatter(
                x=m2_df['date'],
                y=m2_df['monthly_growth'],
                name='Monthly Growth Rate (%)',
                yaxis='y2',
                line=dict(color='#ff7f0e', width=1.5)
            ))
            
            # Set layout with dual Y-axes
            fig.update_layout(
                title='M2 Money Supply - Monthly Data',
                xaxis=dict(title='Date'),
                yaxis=dict(
                    title='M2 Supply (Billions USD)',
                    titlefont=dict(color='#1f77b4'),
                    tickfont=dict(color='#1f77b4')
                ),
                yaxis2=dict(
                    title='Growth Rate (%)',
                    titlefont=dict(color='#ff7f0e'),
                    tickfont=dict(color='#ff7f0e'),
                    anchor='x',
                    overlaying='y',
                    side='right'
                ),
                legend=dict(x=0.01, y=0.99, orientation='h'),
                height=600
            )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Calculate and display key statistics
        if data_type == "Annual":
            st.subheader("Key Statistics")
            
            if "year" in m2_df.columns and "value" in m2_df.columns and "annual_growth" in m2_df.columns:
                # Find years with highest and lowest growth rates
                max_growth_row = m2_df.loc[m2_df['annual_growth'].idxmax()]
                min_growth_row = m2_df.loc[m2_df['annual_growth'].idxmin()]
                
                # Calculate average annual growth rate
                avg_growth = m2_df['annual_growth'].mean()
                
                # Calculate total growth over the period
                if not m2_df.empty and len(m2_df) > 1:
                    first_value = m2_df.iloc[0]['value']
                    last_value = m2_df.iloc[-1]['value']
                    total_growth_pct = ((last_value - first_value) / first_value) * 100
                    
                    # Display statistics
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Average Annual Growth", f"{avg_growth:.2f}%")
                    
                    with col2:
                        st.metric("Highest Growth", 
                               f"{max_growth_row['annual_growth']:.2f}% ({int(max_growth_row['year'])})")
                    
                    with col3:
                        st.metric("Lowest Growth", 
                               f"{min_growth_row['annual_growth']:.2f}% ({int(min_growth_row['year'])})")
                    
                    # Second row of metrics
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Total Growth", f"{total_growth_pct:.2f}%")
                    
                    with col2:
                        st.metric("M2 in First Year", f"${first_value:.2f} Billion")
                    
                    with col3:
                        st.metric("M2 in Last Year", f"${last_value:.2f} Billion")
    else:
        st.warning("No M2 money supply data available for the selected criteria")

with tabs[3]:
    st.header("SQL Workbench")
    st.write("Execute SQL queries directly on the database with enhanced editor")
    
    # SQL editor with syntax highlighting and line numbers
    st.subheader("Write SQL Query")
    
    # Sample queries for quick reference
    with st.expander("Sample Queries (Click to View)"):
        st.markdown("""
        ### Common Queries
        
        #### Tables and Schema Information
        ```sql
        -- List all tables
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name;
        
        -- Column information for a specific table
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'company_metrics'
        ORDER BY ordinal_position;
        ```
        
        #### M2 Money Supply Data
        ```sql
        -- Annual M2 data with highest growth rates
        SELECT year, value, annual_growth
        FROM m2_supply_annual
        ORDER BY annual_growth DESC
        LIMIT 5;
        
        -- Monthly M2 data for 2022
        SELECT date, value, monthly_growth
        FROM m2_supply_monthly
        WHERE year = 2022
        ORDER BY date;
        ```
        
        #### Company Financial Data
        ```sql
        -- Top companies by revenue in 2024
        SELECT company, year, revenue
        FROM company_metrics
        WHERE year = 2024
        ORDER BY revenue DESC;
        
        -- Year-over-year growth for Apple
        SELECT m1.year, m1.revenue, 
        ((m1.revenue - m2.revenue) / m2.revenue * 100) as yoy_growth
        FROM company_metrics m1
        JOIN company_metrics m2 ON m1.company = m2.company AND m1.year = m2.year + 1
        WHERE m1.company = 'Apple'
        ORDER BY m1.year;
        ```
        
        #### Advertising Data
        ```sql
        -- Top countries by ad spend in 2023
        SELECT country, SUM(value) as total_spend
        FROM advertising_data
        WHERE year = 2023
        GROUP BY country
        ORDER BY total_spend DESC
        LIMIT 10;
        
        -- Digital ad growth by year
        SELECT year, SUM(value) as digital_spend
        FROM advertising_data
        WHERE metric_type = 'Digital'
        GROUP BY year
        ORDER BY year;
        ```
        """)
    
    # Load saved queries if they exist
    if 'saved_queries' not in st.session_state:
        st.session_state.saved_queries = {
            "List All Tables": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;",
            "Top Companies by Revenue (2024)": "SELECT company, year, revenue FROM company_metrics WHERE year = 2024 ORDER BY revenue DESC LIMIT 10;"
        }
    
    # Saved queries selector
    saved_queries = list(st.session_state.saved_queries.keys())
    saved_queries.insert(0, "-- Select a saved query --")
    
    selected_saved_query = st.selectbox("Saved Queries:", saved_queries)
    
    # Load selected saved query
    initial_query = ""
    if selected_saved_query != "-- Select a saved query --":
        initial_query = st.session_state.saved_queries[selected_saved_query]
    
    # Create SQL editor
    query_editor = create_text_editor(initial_query, height=200, key="sql_editor")
    
    # Controls for saving queries
    col1, col2 = st.columns([3, 1])
    
    with col1:
        save_query_name = st.text_input("Save query as:", key="save_query_name")
    
    with col2:
        st.write("&nbsp;")  # Spacer
        if st.button("Save Query") and save_query_name and query_editor.strip():
            st.session_state.saved_queries[save_query_name] = query_editor
            st.success(f"Query saved as '{save_query_name}'")
    
    # Execution options
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        execute_clicked = st.button("Execute Query", type="primary")
    
    with col2:
        max_rows = st.number_input("Max rows to display:", min_value=10, max_value=10000, value=100, step=10)
    
    with col3:
        export_format = st.radio("Export format:", ["CSV", "JSON"], horizontal=True)
    
    # Execute the query
    if execute_clicked and query_editor.strip():
        with st.spinner("Executing query..."):
            try:
                # Add LIMIT clause if not already present
                query = query_editor.strip()
                if "LIMIT" not in query.upper() and query.upper().startswith("SELECT"):
                    query += f" LIMIT {max_rows}"
                
                # Execute the query
                result_df = execute_query(query)
                
                # Display results
                if not result_df.empty:
                    st.success(f"Query executed successfully. Returned {len(result_df)} rows.")
                    
                    # Create tabs for different result views
                    result_tabs = st.tabs(["Data Table", "Statistics", "Export"])
                    
                    with result_tabs[0]:
                        st.dataframe(result_df, use_container_width=True)
                    
                    with result_tabs[1]:
                        try:
                            # Generate basic statistics for numeric columns
                            numeric_cols = result_df.select_dtypes(include=['number']).columns
                            
                            if not numeric_cols.empty:
                                st.subheader("Statistics for Numeric Columns")
                                st.dataframe(result_df[numeric_cols].describe(), use_container_width=True)
                                
                                # Create visualizations for numeric data
                                if len(numeric_cols) > 0 and len(result_df) > 1:
                                    st.subheader("Quick Visualization")
                                    
                                    # Allow user to select columns for visualization
                                    if len(result_df.columns) > 1:
                                        x_col = st.selectbox("X-axis column:", result_df.columns)
                                        y_cols = st.multiselect("Y-axis column(s):", numeric_cols)
                                        
                                        if x_col and y_cols:
                                            fig = go.Figure()
                                            
                                            for y_col in y_cols:
                                                fig.add_trace(go.Scatter(
                                                    x=result_df[x_col],
                                                    y=result_df[y_col],
                                                    mode='lines+markers',
                                                    name=y_col
                                                ))
                                            
                                            fig.update_layout(
                                                title=f"Query Results: {y_cols} by {x_col}",
                                                xaxis_title=x_col,
                                                yaxis_title=', '.join(y_cols),
                                                height=400
                                            )
                                            
                                            st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("No numeric columns to analyze")
                        except Exception as e:
                            st.error(f"Error generating statistics: {str(e)}")
                    
                    with result_tabs[2]:
                        st.subheader("Export Results")
                        
                        if export_format == "CSV":
                            csv = result_df.to_csv(index=False)
                            st.download_button(
                                label="Download CSV",
                                data=csv,
                                file_name="query_results.csv",
                                mime="text/csv"
                            )
                        else:
                            json_str = result_df.to_json(orient='records', date_format='iso')
                            st.download_button(
                                label="Download JSON",
                                data=json_str,
                                file_name="query_results.json",
                                mime="application/json"
                            )
                else:
                    st.info("Query executed successfully but returned no results.")
            except Exception as e:
                st.error(f"Error executing query: {str(e)}")
    
    # Add a section for query history
    with st.expander("Query History", expanded=False):
        if 'query_history' not in st.session_state:
            st.session_state.query_history = []
        
        if execute_clicked and query_editor.strip():
            # Add to history if not already there
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            history_entry = {"timestamp": timestamp, "query": query_editor}
            
            # Only add if not a duplicate of the last query
            if not st.session_state.query_history or st.session_state.query_history[-1]["query"] != query_editor:
                st.session_state.query_history.append(history_entry)
                
                # Limit history size
                if len(st.session_state.query_history) > 20:
                    st.session_state.query_history.pop(0)
        
        # Display history
        if st.session_state.query_history:
            for i, entry in enumerate(reversed(st.session_state.query_history)):
                with st.container():
                    col1, col2 = st.columns([1, 6])
                    with col1:
                        if st.button(f"Load #{i+1}", key=f"load_history_{i}"):
                            st.session_state.sql_editor = entry["query"]
                            st.experimental_rerun()
                    with col2:
                        st.text(f"{entry['timestamp']}: {entry['query'][:50]}..." if len(entry['query']) > 50 else entry['query'])

with tabs[4]:
    st.header("Full Database Export")
    st.write("Download the complete financial dashboard database as CSV files or SQL backup.")
    
    # Get all tables
    all_tables_query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
    tables_df = execute_query(all_tables_query)
    
    if not tables_df.empty:
        st.subheader("Available Tables")
        
        # Show table overview with row counts
        table_overview = []
        for _, row in tables_df.iterrows():
            table_name = row['table_name']
            try:
                count_df = execute_query(f"SELECT COUNT(*) as row_count FROM {table_name}")
                row_count = count_df['row_count'].iloc[0] if not count_df.empty else 0
                table_overview.append({"Table Name": table_name, "Row Count": row_count})
            except:
                table_overview.append({"Table Name": table_name, "Row Count": "Error"})
        
        overview_df = pd.DataFrame(table_overview)
        st.dataframe(overview_df, use_container_width=True)
        
        # Export options
        st.subheader("Export Options")
        
        export_tabs = st.tabs(["Individual Tables", "Complete Database", "Consolidated Views"])
        
        with export_tabs[0]:
            st.write("Export individual tables in your preferred format")
            
            # Table selection
            selected_tables = st.multiselect("Select tables to export:", 
                                           [row['table_name'] for _, row in tables_df.iterrows()],
                                           default=[row['table_name'] for _, row in tables_df.iterrows()])
            
            # Export format and options
            col1, col2, col3 = st.columns(3)
            with col1:
                export_format = st.radio("Export format:", ["CSV", "SQL"], key="individual_format")
            with col2:
                include_headers = st.checkbox("Include column headers", value=True)
            with col3:
                max_rows_per_table = st.number_input("Max rows per table (0 = all):", min_value=0, value=0)
            
            if st.button("Generate Export Files"):
                if selected_tables:
                    # Create a zip file with all selected tables
                    import zipfile
                    import io
                    
                    zip_buffer = io.BytesIO()
                    file_extension = "csv" if export_format == "CSV" else "sql"
                    
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for table in selected_tables:
                            try:
                                # Query data
                                limit_clause = f"LIMIT {max_rows_per_table}" if max_rows_per_table > 0 else ""
                                query = f"SELECT * FROM {table} {limit_clause}"
                                table_data = execute_query(query)
                                
                                if not table_data.empty:
                                    if export_format == "CSV":
                                        # Convert to CSV
                                        file_content = table_data.to_csv(index=False, header=include_headers)
                                        zip_file.writestr(f"{table}.csv", file_content)
                                    else:
                                        # Convert to SQL INSERT statements
                                        sql_content = f"-- Data for table: {table}\n"
                                        columns = table_data.columns.tolist()
                                        columns_str = ", ".join(columns)
                                        
                                        for _, data_row in table_data.iterrows():
                                            values = []
                                            for col in columns:
                                                val = data_row[col]
                                                if pd.isna(val):
                                                    values.append("NULL")
                                                elif isinstance(val, (int, float)):
                                                    values.append(str(val))
                                                elif isinstance(val, bool):
                                                    values.append("TRUE" if val else "FALSE")
                                                else:
                                                    escaped_val = str(val).replace("'", "''")
                                                    values.append(f"'{escaped_val}'")
                                            
                                            values_str = ", ".join(values)
                                            sql_content += f"INSERT INTO {table} ({columns_str}) VALUES ({values_str});\n"
                                        
                                        zip_file.writestr(f"{table}.sql", sql_content)
                                else:
                                    # Add empty file for empty tables
                                    zip_file.writestr(f"{table}_EMPTY.{file_extension}", "No data available")
                            except Exception as e:
                                # Add error file
                                zip_file.writestr(f"{table}_ERROR.txt", f"Error exporting table: {str(e)}")
                    
                    zip_buffer.seek(0)
                    
                    st.download_button(
                        label=f"Download All Selected Tables ({export_format}) - ZIP",
                        data=zip_buffer.getvalue(),
                        file_name=f"financial_dashboard_tables_{export_format.lower()}.zip",
                        mime="application/zip"
                    )
                    
                    st.success(f"Generated {export_format} export for {len(selected_tables)} tables")
                else:
                    st.warning("Please select at least one table to export")
        
        with export_tabs[1]:
            st.write("Export the complete database structure and data")
            
            # Database backup options
            col1, col2 = st.columns(2)
            with col1:
                include_structure = st.checkbox("Include table structure (CREATE statements)", value=True)
            with col2:
                include_data = st.checkbox("Include all data (INSERT statements)", value=True)
            
            if st.button("Generate Complete Database Backup"):
                try:
                    # Create SQL dump
                    sql_dump = ""
                    
                    if include_structure:
                        # Add table creation statements
                        for _, row in tables_df.iterrows():
                            table_name = row['table_name']
                            
                            # Get table structure
                            structure_query = f"""
                            SELECT column_name, data_type, is_nullable, column_default
                            FROM information_schema.columns
                            WHERE table_name = '{table_name}' AND table_schema = 'public'
                            ORDER BY ordinal_position
                            """
                            
                            columns_info = execute_query(structure_query)
                            
                            if not columns_info.empty:
                                sql_dump += f"\n-- Table: {table_name}\n"
                                sql_dump += f"CREATE TABLE {table_name} (\n"
                                
                                column_definitions = []
                                for _, col in columns_info.iterrows():
                                    col_def = f"    {col['column_name']} {col['data_type']}"
                                    if col['is_nullable'] == 'NO':
                                        col_def += " NOT NULL"
                                    if pd.notna(col['column_default']):
                                        col_def += f" DEFAULT {col['column_default']}"
                                    column_definitions.append(col_def)
                                
                                sql_dump += ",\n".join(column_definitions)
                                sql_dump += "\n);\n\n"
                    
                    if include_data:
                        # Add data insertion statements
                        for _, row in tables_df.iterrows():
                            table_name = row['table_name']
                            
                            try:
                                table_data = execute_query(f"SELECT * FROM {table_name}")
                                
                                if not table_data.empty:
                                    sql_dump += f"-- Data for table: {table_name}\n"
                                    
                                    # Generate INSERT statements
                                    columns = table_data.columns.tolist()
                                    columns_str = ", ".join(columns)
                                    
                                    for _, data_row in table_data.iterrows():
                                        values = []
                                        for col in columns:
                                            val = data_row[col]
                                            if pd.isna(val):
                                                values.append("NULL")
                                            elif isinstance(val, (int, float)):
                                                values.append(str(val))
                                            elif isinstance(val, bool):
                                                values.append("TRUE" if val else "FALSE")
                                            else:
                                                escaped_val = str(val).replace("'", "''")
                                                values.append(f"'{escaped_val}'")
                                        
                                        values_str = ", ".join(values)
                                        sql_dump += f"INSERT INTO {table_name} ({columns_str}) VALUES ({values_str});\n"
                                    
                                    sql_dump += "\n"
                            except Exception as e:
                                sql_dump += f"-- Error exporting data for {table_name}: {str(e)}\n\n"
                    
                    # Provide download
                    st.download_button(
                        label="Download Complete Database SQL",
                        data=sql_dump,
                        file_name="complete_financial_dashboard.sql",
                        mime="text/plain"
                    )
                    
                    st.success("Generated complete database backup")
                    
                    # Show preview
                    st.subheader("SQL Backup Preview")
                    st.code(sql_dump[:2000] + ("..." if len(sql_dump) > 2000 else ""), language="sql")
                    
                except Exception as e:
                    st.error(f"Error generating database backup: {str(e)}")
        
        with export_tabs[2]:
            st.write("Export consolidated data views combining related information")
            
            # Predefined consolidated views
            consolidated_views = {
                "Company Financial Overview": """
                    SELECT 
                        cm.company,
                        cm.year,
                        MAX(CASE WHEN cm.metric_name = 'revenue' THEN cm.value END) as revenue,
                        MAX(CASE WHEN cm.metric_name = 'net_income' THEN cm.value END) as net_income,
                        MAX(CASE WHEN cm.metric_name = 'cash_balance' THEN cm.value END) as cash_balance,
                        MAX(CASE WHEN cm.metric_name = 'rd' THEN cm.value END) as rd_spending,
                        ec.employee_count,
                        cmc.market_cap,
                        ar.revenue as advertising_revenue
                    FROM company_metrics cm
                    LEFT JOIN employee_counts ec ON cm.company = ec.company AND cm.year = ec.year
                    LEFT JOIN company_market_caps cmc ON cm.company = cmc.company_name AND cm.year = cmc.year
                    LEFT JOIN advertising_revenue ar ON cm.company = ar.company AND cm.year = ar.year
                    GROUP BY cm.company, cm.year, ec.employee_count, cmc.market_cap, ar.revenue
                    ORDER BY cm.company, cm.year
                """,
                
                "Company Segments Summary": """
                    SELECT 
                        company,
                        year,
                        segment_name,
                        value as segment_revenue,
                        percentage as segment_percentage,
                        source
                    FROM company_segments
                    ORDER BY company, year, value DESC
                """,
                
                "Global Advertising Trends": """
                    SELECT 
                        r.name as region,
                        ad.year,
                        ad.metric_type,
                        ad.value
                    FROM advertising_data ad
                    LEFT JOIN regions r ON ad.region_id = r.id
                    ORDER BY r.name, ad.year, ad.metric_type
                """,
                
                "Complete Company Insights": """
                    SELECT 
                        company,
                        year,
                        category,
                        insight
                    FROM company_insights
                    ORDER BY company, year, category
                """,
                
                "Complete Segment Insights (Clean Format)": """
                    SELECT 
                        si.company,
                        si.year,
                        si.segment_name,
                        si.insight,
                        cs.value as segment_revenue
                    FROM segment_insights si
                    LEFT JOIN company_segments cs ON si.company = cs.company 
                        AND si.year = cs.year 
                        AND si.segment_name = cs.segment_name
                    ORDER BY si.company ASC, si.year ASC, si.segment_name ASC
                """
            }
            
            selected_view = st.selectbox("Select a consolidated view:", list(consolidated_views.keys()))
            
            if selected_view:
                # Show query preview
                st.subheader("Query Preview")
                st.code(consolidated_views[selected_view], language="sql")
                
                if st.button(f"Generate {selected_view} Export"):
                    try:
                        result_data = execute_query(consolidated_views[selected_view])
                        
                        if not result_data.empty:
                            # Special handling for segment insights to provide clean format
                            if selected_view == "Complete Segment Insights (Clean Format)":
                                # Create consolidated format - group insights by company/year/segment
                                consolidated_data = []
                                
                                # Sort the result data first
                                result_data_sorted = result_data.sort_values(['company', 'year', 'segment_name'], ascending=[True, True, True])
                                
                                # Group by company, year, and segment_name to consolidate insights
                                grouped = result_data_sorted.groupby(['company', 'year', 'segment_name'])
                                
                                for (company, year, segment), group in grouped:
                                    # Get segment revenue (should be same for all rows in group)
                                    segment_revenue = group['segment_revenue'].iloc[0] if 'segment_revenue' in group.columns else None
                                    
                                    # Consolidate all insights with semicolon separator
                                    insights = group['insight'].tolist()
                                    # Clean up newlines and extra whitespace from insights
                                    cleaned_insights = [insight.replace('\n', ' ').replace('\r', ' ').strip() for insight in insights]
                                    consolidated_insight = ' ; '.join(cleaned_insights)
                                    
                                    consolidated_data.append({
                                        'Company': company,
                                        'Year': year,
                                        'Segment': segment,
                                        'Insight': consolidated_insight,
                                        'Segment_Revenue': segment_revenue
                                    })
                                
                                # Convert to DataFrame 
                                clean_df = pd.DataFrame(consolidated_data)
                                
                                # Generate clean CSV without index
                                csv_data = clean_df.to_csv(index=False)
                                
                                # Show preview of clean format
                                st.subheader("Data Preview (Clean Format):")
                                st.dataframe(clean_df.head(20), use_container_width=True)
                                
                                # Provide download
                                filename = "complete_segment_insights_clean_format.csv"
                                st.download_button(
                                    label=f"Download {selected_view} CSV",
                                    data=csv_data,
                                    file_name=filename,
                                    mime="text/csv"
                                )
                                
                                st.success(f"Generated clean export with {len(clean_df)} segment insights, organized chronologically by company and year")
                            else:
                                # Standard CSV export for other views
                                csv_data = result_data.to_csv(index=False)
                                
                                # Show preview
                                st.subheader("Data Preview")
                                st.dataframe(result_data.head(20), use_container_width=True)
                                
                                # Provide download
                                filename = selected_view.lower().replace(" ", "_").replace("(", "").replace(")", "") + ".csv"
                                st.download_button(
                                    label=f"Download {selected_view} CSV",
                                    data=csv_data,
                                    file_name=filename,
                                    mime="text/csv"
                                )
                                
                                st.success(f"Generated {selected_view} with {len(result_data)} rows")
                        else:
                            st.warning(f"No data found for {selected_view}")
                    except Exception as e:
                        st.error(f"Error generating {selected_view}: {str(e)}")
            
            # Custom consolidated view
            st.subheader("Custom Consolidated View")
            custom_query = create_text_editor(
                "-- Write your custom query to create a consolidated view\nSELECT * FROM company_metrics LIMIT 10;", 
                height=150, 
                key="custom_consolidated_query"
            )
            
            if st.button("Generate Custom Export"):
                if custom_query.strip():
                    try:
                        custom_data = execute_query(custom_query)
                        
                        if not custom_data.empty:
                            csv_data = custom_data.to_csv(index=False)
                            
                            st.download_button(
                                label="Download Custom Query Results",
                                data=csv_data,
                                file_name="custom_consolidated_view.csv",
                                mime="text/csv"
                            )
                            
                            st.success(f"Generated custom export with {len(custom_data)} rows")
                            st.dataframe(custom_data.head(10), use_container_width=True)
                        else:
                            st.info("Custom query returned no results")
                    except Exception as e:
                        st.error(f"Error executing custom query: {str(e)}")
                else:
                    st.warning("Please enter a custom query")
    else:
        st.error("No tables found in the database")

# Add explanatory notes
st.markdown("""
### Notes on M2 Money Supply

M2 is a measure of the money supply that includes cash, checking deposits, savings deposits, 
money market securities, and other time deposits. It is an important economic indicator that reflects 
the amount of money in circulation and can impact inflation, interest rates, and overall economic activity.

#### Key Points:
1. M2 growth often accelerates during economic crises as central banks increase liquidity
2. Periods of high M2 growth may precede inflation with a time lag
3. The Federal Reserve closely monitors M2 as part of monetary policy decisions
4. Historical events like the 2008 financial crisis and 2020 pandemic show significant spikes in M2 growth
""")

# Add disclaimer
st.markdown("""
---
<small>This tool is for development and fine-tuning purposes only.</small>
""", unsafe_allow_html=True)
