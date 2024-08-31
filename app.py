import streamlit as st
import fitz  # PyMuPDF
import easyocr
from pdf2image import convert_from_path
import camelot
import io
from PIL import Image
from groq import Groq
from fpdf import FPDF
import os

# Initialize EasyOCR reader
ocr_reader = easyocr.Reader(['en'])

# Initialize Groq API
GROQ_API_KEY = st.secrets.key.G_api
client = Groq(api_key=GROQ_API_KEY)

# Function to extract text from PDF
def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    extracted_text = ""

    for page_num in range(min(doc.page_count, 50)):  # Limit to 50 pages
        page = doc.load_page(page_num)
        text = page.get_text()
        extracted_text += f"\n\nPage {page_num + 1}\n{text}"

        image_list = page.get_images(full=True)
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            image = Image.open(io.BytesIO(image_bytes))
            
            # Performing OCR on the image using EasyOCR
            ocr_results = ocr_reader.readtext(image)
            ocr_text = " ".join([result[1] for result in ocr_results])
            extracted_text += ocr_text

        # Extracting tables using Camelot
        pdf_file = convert_from_path(pdf_path)
        for i, img in enumerate(pdf_file):
            img.save(f'page_{i}.jpg', 'JPEG')
            tables = camelot.read_pdf(pdf_path, pages=str(page_num + 1))
            for table in tables:
                extracted_text += table.df.to_string()

    return extracted_text

# Function to summarize text using Groq API
def summarize_text(text, model="llama-3.1-70b-versatile"):
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": "Summarize this page in 15-20 lines under the heading of summary. You have to summarize, even if there are different, unlike topics on that page. (Kindly provide the response in proper paragraphing). However, if there is no text, then print Nothing to summarize. Additionally, after summarizing the text, enlist difficult terms up to 15, along with their single line meaning." + text}],
        model=model,
    )
    return chat_completion.choices[0].message.content

# Function to generate PDF
def generate_pdf(summaries):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    for i, summary in enumerate(summaries):
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, f"Summary of Page {i + 1}\n\n" + summary.encode('utf-8').decode('latin-1'))

    pdf_path = "summarized_output.pdf"
    pdf.output(pdf_path)
    return pdf_path

# Streamlit app setup
st.title("PDF Summarizer")
st.write("Upload a PDF file (up to 50 pages) to summarize its content.")

uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file is not None:
    with open("uploaded_file.pdf", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    st.write("Processing the PDF file...")

    # Extract text from PDF
    text = extract_text_from_pdf("uploaded_file.pdf")
    
    st.write("Extracting and summarizing text from each page...")
    
    summaries = []
    total_pages = min(fitz.open("uploaded_file.pdf").page_count, 50)
    
    progress_bar = st.progress(0)
    
    for i, page_text in enumerate(text.split('\n\nPage ')[1:], start=1):
        st.write(f"Processing page {i} of {total_pages}...")
        summary = summarize_text(page_text)
        summaries.append(summary)
        progress_bar.progress(i / total_pages)
    
    # Generate PDF with summaries
    summarized_pdf_path = generate_pdf(summaries)
    
    # Provide download link for the summarized PDF
    with open(summarized_pdf_path, "rb") as f:
        st.download_button("Download Summarized PDF", f, file_name="summarized_output.pdf")
    
    st.success("PDF summarization complete!")
