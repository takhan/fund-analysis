import streamlit as st
import anthropic
import io
import time
import os
import PyPDF2
import base64
import json
import boto3
from io import BytesIO
from openai import OpenAI
from pydantic import BaseModel


def extract_info_from_pdf(path: str, filename: str, items: list[str], pages_per_chunk: int = 3):
    anthropic_client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_KEY"))
    reader = PyPDF2.PdfReader(path)
    total_pages = len(reader.pages)
    print(total_pages)
    # Initialize all to empty lists
    results = {itm: [] for itm in items}
    print(results)
    item_string = ", ".join(items)
    print(path)
    for start in range(0, total_pages, pages_per_chunk):
        end = min(start + pages_per_chunk, total_pages)
        # Split pdf
        writer = PyPDF2.PdfWriter()
        for p in reader.pages[start:end]:
            writer.add_page(p)

        buffer = io.BytesIO()
        writer.write(buffer)
        chunk_bytes = buffer.getvalue()

        # Base64 encode & estimate tokens
        encoded_pdf = base64.b64encode(chunk_bytes).decode("ascii")
        #chunk_tokens = max(1, len(encoded_pdf) // 4)  # ~4 chars = 1 Anthropic token
        #print(chunk_tokens)
        #    (chunk_tokens tokens) / (40 000 tokens/min) ==> minutes, ×60 => seconds
        #wait_secs = chunk_tokens * 60.0 / 40_000.0

        prompt = (
            f"You are an analyst determining whether to invest in a VC fund and are looking through a document that is part of an investment prospectus the fund has provided."
            f"This mini‑PDF covers pages {start+1} to {end} of the original document.\n\n"
            f"You are determining whether each of the following data points appears in the document, "
            f"and on which page(s) of the full document. Reply *only* with nested JSON of the form:\n"
            f"{{data point (exactly as provided in the input): {{value: <info or N/A>, page: [<absolute page nums of the full document> or N/A]}}}}.\n\n"
            f"Data Points: {item_string}"
        )
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": encoded_pdf
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
        message = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=messages
        )
        try:
            resp = json.loads(message.content[0].text)
            for k, info in resp.items():
                if info["value"] != "N/A": #and results[k]["value"] == "N/A":
                  info["data point"] = k
                  info["filename"] = filename
                  results[k].append(info)
        except json.JSONDecodeError:
            # log msg.content[0].text if needed
            pass
        token_count = anthropic_client.messages.count_tokens(model="claude-3-5-sonnet-20241022",messages=messages).input_tokens
        # Sleep just long enough to stay under 40 000 tokens/min
        wait_secs = token_count * 60.0 / 40_000.0
        time.sleep(wait_secs)

    return results

def extract_info_from_pdf_openai(filename, items, doc_dict):
    openai_client = OpenAI(api_key=st.session_state.openai_api_key)

    class DataPointInfo(BaseModel):
        datapointnumber: int
        information: str

    class PDFDataExtraction(BaseModel):
        datapoints: list[DataPointInfo]

    # Initialize all to empty lists
    results = {st.session_state.item_to_index[itm]: [] for itm in items}
    print(items)
    print(results)
    item_string = ""
    for item in items:
        item_string+= "Data Point Number: "+str(st.session_state.item_to_index[item])+" Data Point: "+item+".\n"
    print(item_string)
    #item_string = ", ".join(items)
    for page in doc_dict.keys():
        
        prompt = (
            f"You are an analyst determining whether to invest in a VC fund and are looking through a document that is part of an investment prospectus the fund has provided."
            f"This text has been parsed from one page of the original pdf document.\n\n"
            f"You are determining whether each of the following data points appears on the page, "
            f"The data points are each numbered"
            f"Convert the data into the given structure where each DataPoint info object contains a datapointnumber that is the number of the data point provided and information that is either the information found or N/A:\n"
            f"Data Points: {item_string}\n\n"
            f"Document Text: {doc_dict[page]}"
        )

        response = openai_client.responses.parse(
            model="gpt-4o",
            input=[
                {
                    "role": "system",
                    "content": prompt,
                },
                {"role": "user", "content": "..."},
            ],
            text_format=PDFDataExtraction,
        )
        resp = response.output_parsed.datapoints
        print(resp)
        for datapointinfo in resp:
            if datapointinfo.information != "N/A":
                toAdd = {}
                toAdd["data point"] = st.session_state.index_to_item[datapointinfo.datapointnumber]
                toAdd["value"] = datapointinfo.information
                toAdd["page"] = page
                toAdd["filename"] = filename
                results[datapointinfo.datapointnumber].append(toAdd)

    return results

def extract_info_openai_chunks(filename, items, doc_dict, pages_per_chunk: int = 3):
    openai_client = OpenAI(api_key=st.session_state.openai_api_key)

    class DataPointInfo(BaseModel):
        datapointnumber: int
        information: str
        page: int

    class PDFDataExtraction(BaseModel):
        datapoints: list[DataPointInfo]

    # Initialize all to empty lists
    results = {st.session_state.item_to_index[itm]: [] for itm in items}
    print(items)
    print(results)
    item_string = ""
    for item in items:
        item_string+= "Data Point Number: "+str(st.session_state.item_to_index[item])+" Data Point: "+item+".\n"
    print(item_string)
    #item_string = ", ".join(items)
    total_pages = len(doc_dict.keys())
    #for page in doc_dict.keys():
    start = 0
    end = min(start + pages_per_chunk, total_pages)
    chunkDict = {}
    for key in doc_dict.keys():
        chunkDict[key] = doc_dict[key]
        start+=1
        if start == end:
            doc_text = ""
            for page in chunkDict.keys():
                doc_text+= f"[{page} Document Text: {chunkDict[page]}]\n"
            print("Doc Text: ")
            print(doc_text)
            prompt = (
                f"You are an analyst determining whether to invest in a VC fund and are looking through a document that is part of an investment prospectus the fund has provided."
                f"This text has been parsed from a subset of pages of the original pdf document. The text of each document is labeled with the page number it comes from.\n\n"
                f"You are determining whether each of the following data points appears on the page, "
                f"The data points are each numbered"
                f"Convert the data into the given structure where each DataPoint info object contains a datapointnumber that is the number of the data point provided, information that is either the information found or N/A, and page that is the page number it comes from or 0 if not found.\n"
                f"Data Points: {item_string}\n\n"
                f"Document Text: {doc_text}"
            )

            response = openai_client.responses.parse(
                model="gpt-4o",
                input=[
                    {
                        "role": "system",
                        "content": prompt,
                    },
                    {"role": "user", "content": "..."},
                ],
                text_format=PDFDataExtraction,
            )
            resp = response.output_parsed.datapoints
            print(resp)
            for datapointinfo in resp:
                if datapointinfo.information != "N/A":
                    toAdd = {}
                    toAdd["data point"] = st.session_state.index_to_item[datapointinfo.datapointnumber]
                    toAdd["value"] = datapointinfo.information
                    toAdd["page"] = datapointinfo.page
                    toAdd["filename"] = filename
                    results[datapointinfo.datapointnumber].append(toAdd)
            start+= pages_per_chunk
            end = min(start + pages_per_chunk, total_pages)
            chunkDict = {}

    return results


def extract_info_from_pdf_pagewise(filename, items, doc_dict):
    anthropic_client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_KEY"))

    # Initialize all to empty lists
    results = {st.session_state.item_to_index[itm]: [] for itm in items}
    print(items)
    print(results)
    item_string = ""
    for item in items:
        item_string+= "Data Point Number: "+str(st.session_state.item_to_index[item])+" Data Point: "+item+".\n"
    print(item_string)
    #item_string = ", ".join(items)
    for page in doc_dict.keys():

        prompt = (
            f"You are an analyst determining whether to invest in a VC fund and are looking through a document that is part of an investment prospectus the fund has provided."
            f"This text has been parsed from one page of the original pdf document.\n\n"
            f"You are determining whether each of the following data points appears on the page, "
            f"The data points are each numbered"
            f"Reply *only* with JSON of the form:\n"
            f"{{data point number: information found or N/A>}}.\n\n"
            f"Data Points: {item_string}\n\n"
            f"Document Text: {doc_dict[page]}"
        )
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
        message = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=messages
        )
        try:
            resp = json.loads(message.content[0].text)
            for key, value in resp.items():
                if value != "N/A": #and results[k]["value"] == "N/A":
                    toAdd = {}
                    toAdd["data point"] = st.session_state.index_to_item[int(key)]
                    toAdd["value"] = value
                    toAdd["page"] = page
                    toAdd["filename"] = filename
                    results[int(key)].append(toAdd)
        except json.JSONDecodeError:
            # log msg.content[0].text if needed
            pass
        token_count = anthropic_client.messages.count_tokens(model="claude-3-5-sonnet-20241022",messages=messages).input_tokens
        # Sleep just long enough to stay under 40 000 tokens/min
        wait_secs = token_count * 60.0 / 40_000.0
        time.sleep(wait_secs)

    return results

def get_files():
    s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )

    # Store bucket name
    bucket_name = "takhan-fund-analysis"

    # Store contents of bucket
    objects_list = s3.list_objects_v2(Bucket=bucket_name).get("Contents")
    print(objects_list)
    return [file['Key'] for file in objects_list]

def get_file_stream(file_name):
    s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )

    # Store bucket name
    bucket_name = "takhan-fund-analysis"
    response = s3.get_object(Bucket=bucket_name, Key=file_name)
    file_stream = BytesIO(response['Body'].read())
    return file_stream


def get_data_points():
    s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )
    # Store bucket name
    bucket_name = "takhan-fund-analysis"
    file_name = "Copy of VC Fund Evaluation Template.xlsx"
    response = s3.get_object(Bucket=bucket_name, Key=file_name)
    file_stream = BytesIO(response['Body'].read())
    return file_stream


def clean_pdf_anthropic(file_path):

    RATE_PER_SEC = 40_000.0 / 60.0  
    anthropic_client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_KEY"))
    reader = PyPDF2.PdfReader(file_path)
    total_pages = len(reader.pages)
    print(total_pages)
    return_dict = {}
    last_request = time.monotonic()
    for i in range(total_pages):
        # Split pdf
        writer = PyPDF2.PdfWriter()
        writer.add_page(reader.pages[i])
        buffer = io.BytesIO()
        writer.write(buffer)
        chunk_bytes = buffer.getvalue()

        # Base64 encode & estimate tokens
        encoded_pdf = base64.b64encode(chunk_bytes).decode("ascii")

        # Load from a local file
        #pdf_data = base64.standard_b64encode(file.read()).decode("utf-8")
        messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": encoded_pdf
                            }
                        },
                        {
                            "type": "text",
                            "text": f"You are converting a pdf presentation that comes from an investment prospectus into text. This is one page of the original document. Describe any images, graphs, or other visuals that are on the page. Return only the description of the page in detail, but no additional commentary."
                        }
                    ]
                }
        ]

        token_count = anthropic_client.messages.count_tokens(model="claude-3-5-sonnet-20241022",messages=messages).input_tokens
        needed = token_count / RATE_PER_SEC
        now = time.monotonic()
        elapsed = now - last_request
        # Sleep just long enough to stay under 40 000 tokens/min
        #wait_secs = token_count * 60.0 / 40_000.0
        #time.sleep(wait_secs)
        to_sleep = needed - elapsed
        if to_sleep > 0:
            time.sleep(to_sleep)

        message = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=messages
        )
        last_request = time.monotonic()
        page_num = "Page Number: "+str(i+1)
        return_dict[page_num] = message.content[0].text
        #print(pdf_text)
    return return_dict

def clean_pdf_openai(file_path, file_name):
    openai_client = OpenAI(api_key=st.session_state.openai_api_key)
    reader = PyPDF2.PdfReader(file_path)
    total_pages = len(reader.pages)
    print(total_pages)
    return_dict = {}
    for i in range(total_pages):
        # Split pdf
        writer = PyPDF2.PdfWriter()
        writer.add_page(reader.pages[i])
        buffer = io.BytesIO()
        writer.write(buffer)
        chunk_bytes = buffer.getvalue()

        # Base64 encode & estimate tokens
        encoded_pdf = base64.b64encode(chunk_bytes).decode("utf-8")

        # Load from a local file
        #pdf_data = base64.standard_b64encode(file.read()).decode("utf-8")
        messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_file",
                            "filename": f"{file_name}",
                            "file_data": f"data:application/pdf;base64,{encoded_pdf}"
                           
                        },
                        {
                            "type": "input_text",
                            "text": f"You are converting a pdf presentation that comes from an investment prospectus into text. This is one page of the original document. Also describe any information images, graphs, or other visuals that are on the page. However, do not mention any purely aesthetic information e.g. colors, font or formatting information e.g. page numbers. Return only the text of the page in detail, but no additional commentary."
                        }
                    ]
                }
        ]


        response = openai_client.responses.create(
            model="gpt-4.1-mini",
            input=messages
        )

        page_num = "Page Number: "+str(i+1)
        print(response.output_text)
        return_dict[page_num] = response.output_text
        #print(pdf_text)
    return return_dict


def process_group_with_openai(datapoint, group_df):
    openai_client = OpenAI(api_key=st.session_state.openai_api_key)
    rows = group_df.to_dict(orient="records")
    rows_json = json.dumps(rows, indent=2)

    prompt = f"""
You are analyzing rows from a document extraction process. Each row has a data point, value, page number, and filename. Determine if the rows represent duplicate or distinct information.

- If the `value` fields are similar enough to be considered duplicates, return a single row using the first value and concatenated pages and filenames.
- If the `value` fields are meaningfully different, merge the values with " / ", and do the same for pages and filenames.

Input rows:
{rows_json}

Output:
Return a single JSON object like:
{{"data point": "...", "value": "...", "page": "...", "filename": "..."}}
"""

    response = openai_client.responses.create(
        model="gpt-4o",
        input=[
            {"role": "system", "content": prompt}
        ],
        text={ "format": {"type": "json_object"} }
    )

    result = response.output[0].content[0].text
    print(result)
    return json.loads(result)