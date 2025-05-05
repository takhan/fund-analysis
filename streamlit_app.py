import streamlit as st
from document_parsing import extract_info_openai_chunks, get_files, get_file_stream, get_data_points, extract_info_from_pdf_pagewise, clean_pdf_anthropic, clean_pdf_openai, extract_info_from_pdf_openai, process_group_with_openai
import pandas as pd
import boto3
import os
import json
from pathlib import Path

if "data_frame" not in st.session_state:
    st.session_state.data_frame = None

if "pdf_data" not in st.session_state:
    st.session_state.pdf_data = {}

if "index_to_item" not in st.session_state:
    st.session_state.index_to_item = {}

if "item_to_index" not in st.session_state:
    st.session_state.item_to_index = {}

if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = os.getenv("OPENAI_KEY")

if "csv" not in st.session_state:
    st.session_state.csv = None

if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []

if "file_mapping" not in st.session_state:
    st.session_state.file_mapping = {"Stage 2 Capital":""}

if "data_excel" not in st.session_state:
    st.session_state.data_excel = None

@st.cache_data
def convert_df(df):
   return df.to_csv(index=False).encode('utf-8')

def deduplicate_dataframe():
    grouped = st.session_state.data_frame.groupby("data point")
    processed_rows = []

    for datapoint, group in grouped:
        result = process_group_with_openai(datapoint, group)
        processed_rows.append(result)

    return pd.DataFrame(processed_rows)

st.title("Fund Analysis")

data_excel = st.file_uploader("Upload a new excel")

if st.button("Update Excel"):
    if data_excel:
        st.session_state.data_excel = data_excel
    st.toast("Excel Updated")

st.subheader("View Existing Fund Files")
st.selectbox("Pick from previously analyzed projects", options=["Stage 2 Capital"])

st.subheader("Or Analyze New Files")

uploaded_pdfs = st.file_uploader(
    "Upload pdf files",
    type = ['pdf'],
    accept_multiple_files=True
)

if uploaded_pdfs:
    if len(st.session_state.uploaded_files)==0:
        st.session_state.uploaded_files.extend(uploaded_pdfs)

fund_label = st.text_input(label="Enter the fund name", value="XYZ Ventures")

if st.button("Parse PDFs"):
    if len(st.session_state.uploaded_files)==0:
        with st.spinner("Parsing PDFs"):
            if os.path.exists('stage_2_capital.json'):
                try:
                    with open('parsed_text_openai.json', 'r') as json_file:
                        st.session_state.pdf_data = json.load(json_file)
                except FileNotFoundError:
                    print(f"Error: File not found: {'parsed_text.json'}")
                except json.JSONDecodeError:
                    print(f"Error: Invalid JSON format in: {'parsed_text.json'}")
            else:
                directory_files = get_files()
                for file in directory_files:
                    if file.endswith('.pdf'):
                        print(file)
                        file_stream = get_file_stream(file)
                        file_text_dict = clean_pdf_openai(file_stream, file)
                        st.session_state.pdf_data[file] = file_text_dict
                        print(file_text_dict)
                with open('parsed_text_openai.json', 'w') as fp:
                    json.dump(st.session_state.pdf_data, fp)
            st.toast("PDFs Parsed")
    else:
        with st.spinner("Parsing PDFs"):
            json_file_name = fund_label+".json"
            if not os.path.exists(json_file_name):
                for file in st.session_state.uploaded_files:
                    file_text_dict = clean_pdf_openai(file, file.name)
                    st.session_state.pdf_data[file.name] = file_text_dict
                
                with open(json_file_name, 'w') as fp:
                    json.dump(st.session_state.pdf_data, fp)
            else:
                try:
                    with open(json_file_name, 'r') as json_file:
                        st.session_state.pdf_data = json.load(json_file)
                except FileNotFoundError:
                    print(f"Error: File not found: {'parsed_text.json'}")
                except json.JSONDecodeError:
                    print(f"Error: Invalid JSON format in: {'parsed_text.json'}")

            st.toast("PDFs Parsed")

if st.button("Analyze Files"):
    if len(st.session_state.uploaded_files)>0:  
        print(st.session_state.pdf_data)
        if not st.session_state.data_excel:
            data_points_file = get_data_points()
            df = pd.read_excel(data_points_file)
        else:
            df = pd.read_excel(st.session_state.data_excel)
        items_full = df["Item"]
        items = []
        for item in items_full:
            if item not in items:
                items.append(item)
        print(items)
        test_items = items[-10:]
        output_info = {}
        i=0
        for item in items:
            #output_info[item] = {"value":"N/A", "page":"N/A"}
            output_info[item] = []
            st.session_state.index_to_item[i] = item
            st.session_state.item_to_index[item] = i
            i+=1

        for file in st.session_state.pdf_data.keys():
            if file.endswith('.pdf'):
                #file_stream = get_file_stream(file)
                #file_text = clean_pdf_anthropic(file_stream)
                num_items = 15
                item_length = len(items)
                items_to_check = []
                for i in range(item_length):
                    #if output_info[items[i]]["value"] == "N/A":
                    if len(output_info[items[i]])==0:
                        items_to_check.append(items[i])
                    if len(items_to_check) == num_items:
                        print(items_to_check)
                        return_dict = extract_info_from_pdf_openai(file, items_to_check, st.session_state.pdf_data[file])
                        #return_dict = extract_info_openai_chunks(file, items_to_check, st.session_state.pdf_data[file])
                        print(return_dict)
                        for key in return_dict.keys():
                            if len(return_dict[key])>0:
                                output_info[st.session_state.index_to_item[key]] = return_dict[key]

                        items_to_check = []
                    elif i==(item_length-1):
                        if len(items_to_check)>0:
                            return_dict = extract_info_from_pdf_openai(file, items_to_check, st.session_state.pdf_data[file])
                            #return_dict = extract_info_openai_chunks(file, items_to_check, st.session_state.pdf_data[file])
                        print(return_dict)
                        for key in return_dict.keys():
                            if len(return_dict[key])>0:
                                output_info[st.session_state.index_to_item[key]] = return_dict[key]
        
        df_list = []
        for data_point in output_info.keys():
            df_list.extend(output_info[data_point])
        df = pd.DataFrame(df_list)
        print(df)
        st.session_state.data_frame = df
        csv_file_name = fund_label+".csv"
        df.to_csv(csv_file_name, index=False)
        deduped_df = deduplicate_dataframe()
        #st.dataframe(deduped_df)
        st.session_state.csv = convert_df(deduped_df)
        st.session_state.data_frame = deduped_df
    elif os.path.exists('stage_2_capital.csv'):
        loaded_df = pd.read_csv('stage_2_capital.csv')
        st.session_state.data_frame = loaded_df
        #deduped_df = deduplicate_dataframe()
        #st.dataframe(deduped_df)
            

        st.session_state.csv = convert_df(st.session_state.data_frame)
        #st.session_state.data_frame = deduped_df

if st.session_state.data_frame is not None:
    st.dataframe(st.session_state.data_frame)

if st.session_state.csv:
    st.download_button(
    "Download CSV",
    st.session_state.csv,
    "file.csv",
    "text/csv",
    key='download-csv'
    )



