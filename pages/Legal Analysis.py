import streamlit as st
from document_parsing import get_files, get_file_stream
import PyPDF2
from openai import OpenAI
import os

st.title("Legal Analysis")

if "legal_docs" not in st.session_state:
    st.session_state.legal_docs = None

if "stds" not in st.session_state:
    st.session_state.stds = None

if "uploaded_lpa" not in st.session_state:
    st.session_state.uploaded_lpa = None

def parseLegalDocs(legal_docs):
    openai_client = OpenAI(api_key=st.session_state.openai_api_key)
    docLength = len(legal_docs)
    docText = ""
    i = 0
    for doc in legal_docs:
        docText += "Document "+str(i)+" : \n\n"+doc
        i+=1
    prompt = (
            f"You are a legal analyst going through several Limited Partners Agreements that VC funds have sent your firm which is evaluating an investment in the funds."
            f"This text below comes from {docLength} different agreements.\n\n"
            f"For each major section or sub topic in the agreements, you are trying to determine what constitues standard terms, rates, or fees."
            f"Reply with a list of each topic/heading that is common to the agreements and what the standard terms/values are for that topic."
            f"Document Text: {docText}"
        )
    messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt
                        }
                    ]
                }
        ]
    response = openai_client.responses.create(
            model="gpt-4.1",
            input=messages
        )
    return response.output_text

def analyzeStandards():
    openai_client = OpenAI(api_key=st.session_state.openai_api_key)
    print(type(st.session_state.stds)) 
    print(type(st.session_state.uploaded_lpa)) 
    prompt = (
            f"You are a legal analyst going through the following Limited Partners Agreements that a VC fund has sent your firm which is evaluating an investment in the fund."
            f"This text below comes from a set of standard terms, rates, and fees that you have created after analyzing previous Limited Partner Agreements.\n\n"
            f"For each major section or sub topic in the standards, you are trying to determine whether this agreement meets or falls outside those standards."
            f"Reply with a list of each subtopic in the standards and a checkmark or if the standards are met or not met plus an explanation of why or why not."
            f"Standards: {st.session_state.stds}.\n\n"
            f"LPA: {st.session_state.uploaded_lpa}"
        )
    print(type(prompt))
    messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt
                        }
                    ]
                }
        ]
    
    response = openai_client.responses.create(
            model="gpt-4.1",
            input=messages
        )
    return response.output_text

if st.button("Compare Files"):
    legal_docs = []
    legal_files = get_files("takhan-legal-files")
    for file in legal_files:
        file_stream = get_file_stream(file, "takhan-legal-files")
        reader = PyPDF2.PdfReader(file_stream)
        text = ""
        for page in reader.pages:
            text+= page.extract_text()
        legal_docs.append(text)
    print(legal_docs)
    st.session_state.legal_docs = legal_docs

    if os.path.exists("Legal_Standards.md"):
        with open('Legal_Standards.md', 'r') as legal_file:
            content = legal_file.read()
            st.session_state.stds = content
    else:
        st.session_state.stds = parseLegalDocs(st.session_state.legal_docs)

uploaded_pdf = st.file_uploader(
    "Upload LPA",
    type = ['pdf']
)

if uploaded_pdf and st.session_state.stds:
    if st.button("Analyze Agreement"):
        reader = PyPDF2.PdfReader(uploaded_pdf)
        text = ""
        for page in reader.pages:
            text+= page.extract_text()
        st.session_state.uploaded_lpa = text
        analysis = analyzeStandards()
        col1, col2, = st.columns(2)
        with col1:
            st.write(st.session_state.stds)
        with col2:
            st.write(analysis)
elif st.session_state.stds:
    st.write(st.session_state.stds)


