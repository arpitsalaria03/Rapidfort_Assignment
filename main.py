from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from docx2pdf import convert
from PyPDF2 import PdfReader, PdfWriter
import os
import uuid
import json
from datetime import datetime

app = FastAPI()

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "output"
MAPPING_FILE = "file_mapping.json"
FILE_MAPPING = {}

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

if os.path.exists(MAPPING_FILE):
    with open(MAPPING_FILE, "r") as f:
        FILE_MAPPING = json.load(f)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def save_file_mapping():
    with open(MAPPING_FILE, "w") as f:
        json.dump(FILE_MAPPING, f)

def generate_id():
    return str(uuid.uuid4())

def add_password_protection(input_pdf, output_pdf, password):
    writer = PdfWriter()
    reader = PdfReader(input_pdf)
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password)
    with open(output_pdf, "wb") as file:
        writer.write(file)

@app.post("/convert/")
async def convert_to_pdf(file: UploadFile = File(...), password: str = Form(None)):
    original_filename = file.filename

    file_id = generate_id()

    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.docx")
    output_pdf_path = os.path.join(OUTPUT_DIR, f"{file_id}.pdf")

    with open(file_path, "wb") as f:
        f.write(await file.read())

    FILE_MAPPING[original_filename] = file_id
    save_file_mapping()

    try:
        convert(file_path, output_pdf_path)

        if password:
            password_protected_path = os.path.join(OUTPUT_DIR, f"{file_id}_protected.pdf")
            add_password_protection(output_pdf_path, password_protected_path, password)
            os.remove(output_pdf_path)
            output_pdf_path = password_protected_path

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during PDF conversion: {str(e)}")

    file_size_kb = round(os.path.getsize(file_path) / 1024, 2)
    timestamp = datetime.now().isoformat()

    return {
        "message": "File converted and ready for download",
        "filename": original_filename,
        "file_size": f"{file_size_kb} KB",
        "timestamp": timestamp,
    }

@app.get("/download/")
async def download_file(filename: str):
    if filename not in FILE_MAPPING:
        raise HTTPException(status_code=404, detail="File not found")

    file_id = FILE_MAPPING[filename]

    protected_file_path = os.path.join(OUTPUT_DIR, f"{file_id}_protected.pdf")
    regular_file_path = os.path.join(OUTPUT_DIR, f"{file_id}.pdf")
    print(protected_file_path)
    print(regular_file_path)
    if os.path.exists(protected_file_path):
        return FileResponse(protected_file_path, media_type="application/pdf", filename=f"{file_id}_protected.pdf")

    if os.path.exists(regular_file_path):
        return FileResponse(regular_file_path, media_type="application/pdf", filename=f"{file_id}.pdf")

    raise HTTPException(status_code=404, detail="File not found")

@app.delete("/delete/")
async def delete_files(filename: str):
    if filename not in FILE_MAPPING:
        raise HTTPException(status_code=404, detail="File not found")

    file_id = FILE_MAPPING[filename]

    docx_file_path = os.path.join(UPLOAD_DIR, f"{file_id}.docx")
    pdf_file_path = os.path.join(OUTPUT_DIR, f"{file_id}.pdf")
    protected_pdf_path = os.path.join(OUTPUT_DIR, f"{file_id}_protected.pdf")

    if os.path.exists(docx_file_path):
        os.remove(docx_file_path)
    if os.path.exists(pdf_file_path):
        os.remove(pdf_file_path)
    if os.path.exists(protected_pdf_path):
        os.remove(protected_pdf_path)

    del FILE_MAPPING[filename]
    save_file_mapping()
    return {"message": "Files deleted successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
