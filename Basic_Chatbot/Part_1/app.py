from flask import Flask, jsonify, request, render_template
from google import genai
import io
import re

app = Flask(__name__)

# Initialize the client with the API key
api_key = "AIzaSyAJMmA0-OC8EFYj7G2nkVpAFG9ggxJW4YU"
client = genai.Client(api_key=api_key)

uploaded_files = []  # Store uploaded files globally
chat_history = []  # Store chat messages globally

def parse_table_to_html(text_table):
    """Convert plain text tables into properly formatted HTML tables."""
    # Split the text into lines
    lines = text_table.strip().split("\n")
    
    # Separate tables and non-table text
    html_output = ""
    current_table = []
    for line in lines:
        if "|" in line:  # Detect table rows
            current_table.append(line)
        else:
            if current_table:
                # Process the current table
                html_output += convert_table_to_html(current_table)
                current_table = []
            html_output += f"<p>{line.strip()}</p>"  # Add non-table text as a paragraph

    # Process any remaining table
    if current_table:
        html_output += convert_table_to_html(current_table)

    return html_output

def convert_table_to_html(table_lines):
    """Convert a list of table lines into an HTML table."""
    html_table = "<table border='1' style='border-collapse: collapse; width: 100%; text-align: left;'>"
    for i, row in enumerate(table_lines):
        columns = [col.strip() for col in row.strip('|').split('|')]
        tag = "th" if i == 0 or row.startswith(":") else "td"  # Use <th> for headers
        html_table += "<tr>" + "".join(f"<{tag}>{col}</{tag}>" for col in columns) + "</tr>"
    html_table += "</table><br>"  # Add spacing after the table
    return html_table

@app.route('/', methods=['GET', 'POST'])
def home():
    global uploaded_files, chat_history

    if request.method == 'POST':
        if 'upload_file' in request.form:  # Handle file upload
            try:
                file = request.files['file']
                doc_data = io.BytesIO(file.read())

                # Upload file to the generative AI client
                uploaded_file = client.files.upload(
                    file=doc_data,
                    config=dict(mime_type='application/pdf')
                )
                uploaded_files.append(uploaded_file)
                chat_history.append({"sender": "system", "message": f"File '{file.filename}' uploaded successfully!"})
                return render_template('chat.html', chat_history=chat_history, uploaded_files=uploaded_files)
            except Exception as e:
                chat_history.append({"sender": "system", "message": f"Error: {str(e)}"})
                return render_template('chat.html', chat_history=chat_history, uploaded_files=uploaded_files)

        elif 'submit_query' in request.form:  # Handle user query
            try:
                query = request.form['query']
                chat_history.append({"sender": "user", "message": query})
                if not uploaded_files:
                    chat_history.append({"sender": "system", "message": "No files uploaded yet!"})
                    return render_template('chat.html', chat_history=chat_history, uploaded_files=uploaded_files)

                # Generate content based on the query and uploaded files
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=uploaded_files + [query]
                )

                # Format the bot's response for better readability
                response_text = format_response(response.text)

                # Append the bot's response to the chat history
                chat_history.append({"sender": "bot", "message": response_text})
                return render_template('chat.html', chat_history=chat_history, uploaded_files=uploaded_files)
            except Exception as e:
                chat_history.append({"sender": "system", "message": f"Error: {str(e)}"})
                return render_template('chat.html', chat_history=chat_history, uploaded_files=uploaded_files)

    # Render the chatbot interface
    return render_template('chat.html', chat_history=chat_history, uploaded_files=uploaded_files)


def format_response(response_text):
    """Format the bot's response for better readability."""
    formatted_response = response_text.replace("**", "<strong>").replace("*", "<em>")
    formatted_response = formatted_response.replace("\n", "<br>")
    return formatted_response

if __name__ == '__main__':
    app.run(debug=True)
