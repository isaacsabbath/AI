import google.generativeai as genai
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def connect_database():
    # Fetch environment variables or use default values if not set
    connector = mysql.connector.connect(
        host = os.getenv('DB_HOST'),
        user = os.getenv('DB_USER'),
        password = os.getenv('DB_PASSWORD'),
        database = os.getenv('DB_NAME'),
    )

    return connector

def query_gen_ai(prompt):
    genai.configure(api_key=os.environ["GENAI_API_KEY"], transport='rest')

    # Create the model
    generation_config = {
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
        "response_mime_type": "text/plain",
    }

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-exp",
        generation_config=generation_config,
    )

    chat_session = model.start_chat()

    response = chat_session.send_message({"parts": [{"text": prompt}]})
    
    # Extract the response text
    return response.text.strip()



def get_table_info():
    """Retrieve table names and column information from the database."""
    connector = connect_database()
    cursor = connector.cursor()

    cursor.execute("""
        SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
        ORDER BY table_name, ordinal_position
    """)

    tables = cursor.fetchall()
    connector.close()

    table_info = {}
    for table_name, column_name, data_type in tables:
        if table_name not in table_info:
            table_info[table_name] = []
        table_info[table_name].append({"name": column_name, "type": data_type})
    return table_info

def build_dynamic_prompt(user_question, tables_info):
    """Construct a prompt for the Gemini API to generate SQL queries."""
    table_prompt = "Available tables and columns in the car database:\n"
    tables = get_table_info()
    for table in tables:
        table_prompt += f"{table} has columns: " + ', '.join([f"{column['name']} ({column['type']})" for
        column in tables[table]]) + "\n"

    prompt = f"""
You are an expert database assistant for a car dealership, known for your detailed and helpful explanations. Information about cars is stored in the following tables:
{table_prompt}

Your task:
1. Analyze the user's question to understand the data they want.
2. Generate a syntactically correct SQL query that uses the appropriate tables and columns.
3. The SQL query should strictly follow standard SQL syntax and only retrieve data without modifying the database.
4. Provide a brief and friendly explanation of why this query is suitable, helping the user understand the logic behind it.
5. Include no additional information beyond the query itself and the brief explanation.

User Question: "{user_question}"

Return the SQL query and the explanation.
"""
    return prompt.strip()



def clean_sql_query(query):
    cleaned_query = query.strip()

    # Remove the ```sql markers if they exist
    if cleaned_query.startswith("```sql"):
        cleaned_query = cleaned_query[6:].strip()  # Remove the ```sql part
    if cleaned_query.endswith("```"):
        cleaned_query = cleaned_query[:-3].strip()  # Remove the ending ```

    return cleaned_query



def execute_query(query):
    """Execute the generated SQL query and return results."""
    connector = connect_database()
    cursor = connector.cursor()

    cleaned_query = clean_sql_query(query)
    
    try:
        cursor.execute(cleaned_query)
        rows = cursor.fetchall()
        results = [dict(zip([col[0] for col in cursor.description], row)) for row in rows]
    except Exception as e:
        results = {"error": str(e)}
    finally:
        connector.close()

    return results


def main():
    """Main chatbot flow."""
    user_question = input("Ask a question about the car database: ")

    # Step 1: Fetch table information
    tables_info = get_table_info()

    # Step 2: Build prompt for Gemini API
    prompt = build_dynamic_prompt(user_question, tables_info)

    # Step 3: Get SQL query from Gemini API
    sql_query = query_gen_ai(prompt)
    print(f"Generated SQL Query: {sql_query}")

    cleaned_query = clean_sql_query(sql_query)
    # Step 4: Execute the query and display results
    query_results = execute_query(sql_query)
    print("Query Results:")
    print(query_results)

if __name__ == "__main__":
    main()



