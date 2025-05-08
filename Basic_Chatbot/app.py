from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from PyPDF2 import PdfReader
import google.generativeai as genai
import io
from pathlib import Path
from pdf2image import convert_from_bytes

app = FastAPI()

# Gemini API key (replace with your actual key)
GEMINI_API_KEY = " "

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# Store PDF text
pdf_text = ""

# Directory to store extracted images
IMAGE_DIR = Path("extracted_images")
IMAGE_DIR.mkdir(exist_ok=True)

# Mount static files to serve images
app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")

# HTML for the frontend
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Question Answering</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f9f9f9;
            color: #333;
        }
        .container {
            max-width: 700px;
            margin: 50px auto;
            padding: 20px;
            background: #fff;
            border-radius: 10px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
        }
        h1 {
            color: #4CAF50;
            font-size: 24px;
            margin-bottom: 20px;
        }
        input, button {
            margin: 10px 0;
            padding: 12px;
            width: 100%;
            border: 1px solid #ccc;
            border-radius: 5px;
            font-size: 16px;
        }
        button {
            background-color: #4CAF50;
            color: white;
            border: none;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover {
            background-color: #45a049;
        }
        #answer {
            margin-top: 20px;
            padding: 15px;
            background: #e8f5e9;
            border: 1px solid #c8e6c9;
            border-radius: 5px;
            text-align: left;
            font-size: 16px;
            line-height: 1.5;
        }
        #message {
            margin-top: 20px;
            color: red;
            font-size: 14px;
        }
        .error {
            color: red;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>PDF Question Answering</h1>
        <form id="uploadForm" action="/upload-pdf/" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept="application/pdf" required>
            <button type="submit">Upload PDF</button>
        </form>
        <form id="questionForm" action="/ask-question/" method="post">
            <input type="text" id="questionInput" name="question" placeholder="Ask a question about the PDF" required>
            <button type="submit">Ask Question</button>
        </form>
        <div id="message"></div>
        <div id="answer"></div>
    </div>
    <script>
        // Handle form submissions with fetch
        document.querySelectorAll('form').forEach(form => {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(form);
                const action = form.action;
                const messageDiv = document.getElementById('message');
                const answerDiv = document.getElementById('answer');
                
                try {
                    const response = await fetch(action, { method: 'POST', body: formData });
                    const result = await response.json();
                    if (action.includes('upload-pdf')) {
                        messageDiv.textContent = result.message;
                        messageDiv.className = '';
                        answerDiv.textContent = '';
                    } else {
                        // Render HTML content in the answer div
                        answerDiv.innerHTML = `<strong>Answer:</strong><br>${result.answer}`;
                        messageDiv.textContent = '';
                    }
                } catch (error) {
                    messageDiv.textContent = 'Error: ' + (error.message || 'Something went wrong');
                    messageDiv.className = 'error';
                }
            });
        });

        // Allow pressing "Enter" to submit the question form
        document.getElementById('questionInput').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                document.getElementById('questionForm').dispatchEvent(new Event('submit'));
            }
        });
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def get_home():
    return HTML_CONTENT

@app.post("/upload-pdf/")
async def upload_pdf(file: UploadFile = File(...)):
    global pdf_text
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    try:
        content = await file.read()
        pdf_reader = PdfReader(io.BytesIO(content))
        pdf_text = ""
        for page in pdf_reader.pages:
            pdf_text += page.extract_text() or ""

        # Extract images from the PDF
        images = convert_from_bytes(content)
        for i, image in enumerate(images):
            image_path = IMAGE_DIR / f"page_{i + 1}.png"
            image.save(image_path, "PNG")

        return {"message": "PDF uploaded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")

@app.post("/ask-question/")
async def ask_question(question: str = Form(...)):
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
    if not pdf_text:
        raise HTTPException(status_code=400, detail="Upload a PDF first")

    try:
        if "show me the pictures" in question.lower() or "figures" in question.lower():
            # Return URLs of extracted images
            image_urls = [f"/images/{image.name}" for image in IMAGE_DIR.iterdir()]
            if not image_urls:
                return {"answer": "No images or figures were found in the uploaded PDF."}
            
            # Provide a list of all extracted images
            images_html = "".join([f'<img src="{url}" alt="Extracted Image" style="max-width: 100%; margin: 10px 0;">' for url in image_urls])
            return {"answer": f"<strong>Extracted Figures:</strong><br>{images_html}"}

        # Default text-based response
        prompt = f"PDF Content: {pdf_text}\n\nQuestion: {question}"
        response = model.generate_content(prompt)
        answer = response.text
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calling Gemini API: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
