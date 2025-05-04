import streamlit as st
from document_parsing import extract_info_from_pdf, get_files, get_file_stream, get_data_points
import pandas as pd

if "data_frame" not in st.session_state:
    st.session_state.data_frame = None

st.title("Fund Analysis")


if st.button("Analyze Files"):
    data_points_file = get_data_points()
    df = pd.read_excel(data_points_file)
    items = df["Item"]
    print(items)
    directory_files = get_files()
    test_files = []
    output_info = {}
    for item in items:
        #output_info[item] = {"value":"N/A", "page":"N/A"}
        output_info[item] = []
        test_files = directory_files[-10:]
    print(test_files)
    for file in test_files:
        if file.endswith('.pdf'):
            num_items = 15
            item_length = len(items)
            items_to_check = []
            for i in range(item_length):
                #if output_info[items[i]]["value"] == "N/A":
                if len(output_info[items[i]])==0:
                    items_to_check.append(items[i])
                if len(items_to_check) == num_items:
                    
                    file_stream = get_file_stream(file)
                    return_dict = extract_info_from_pdf(file_stream, file, items_to_check)
                    print(return_dict)
                    for key in return_dict.keys():
                        if len(return_dict[key])>0:
                            output_info[key] = return_dict[key]

                    items_to_check = []
                elif i==(item_length-1):
                    if len(items_to_check)>0:
                        file_stream = get_file_stream(file)
                        return_dict = extract_info_from_pdf(file_stream, file, items_to_check)
                    print(return_dict)
                    for key in return_dict.keys():
                        if len(return_dict[key])>0:
                            output_info[key] = return_dict[key]
    
    df_list = []
    for data_point in output_info.keys():
        df_list.extend(output_info[data_point])
    df = pd.DataFrame(df_list)
    print(df)
    st.session_state.data_frame = df
    st.dataframe(df)
    df.to_csv('output.csv', index=False)
    print(output_info)



