import boto3
import json
import pandas as pd
import s3fs

from datetime import datetime


client = boto3.client('sagemaker-runtime')

endpoint_name = "insight-bert-2023-11-13-20-40-49-689"                                      
content_type = "application/list-text"  # The MIME type of the input data in the request body.
accept = "application/json" 
s3_input_file_path1 ='s3://abb8-ml-model/dailydownload/mailContents.json'
s3_input_file_path ='./mailContents.json'
s3_output_file_path ='s3://abb8-ml-model/dailydownload/insights.json'
s3_prompt_questions_path='./questions.txt'

def create_payload(question,text):       
    input_data=[''+question+'',''+text+'']    
    return input_data

def parse_response(response,score_threshold):    
    answer = json.loads(response['Body'].read().decode())
    #print(answer)
    if answer['score'] > score_threshold:
        return answer['answer']
    else:
        return 'NA'

def call_endpoint(input_data):
    payload =json.dumps(input_data).encode("utf-8")    
    response = client.invoke_endpoint(
        EndpointName=endpoint_name, 
        CustomAttributes="", 
        ContentType=content_type,
        Accept=accept,
        Body=payload
        )
    answer=parse_response(response,.05)
    return answer
    
def process_files():
    docs = pd.read_json(s3_input_file_path1)
    docs.insert(3,"insight_dates","")
    docs.insert(4,"summary","")
    return docs
    #print(docs.head(1))
    #print(questions.head(1))


def run_insight():
    docs= process_files()
    questions=pd.read_csv(s3_prompt_questions_path)
    df = pd.DataFrame(columns=['thread_id','text', 'label'])
    result_df= pd.DataFrame(columns=['id','title', 'description','type','status','documents','pocID','poc','url','actionDate','location','createdDate','updatedDate'])
    for index,row in docs.iterrows():
        id=row["thread_id"]
        title=row["mail_subject"]
        #description=
        #'type','status','documents','pocID','poc','url','actionDate','location','createdDate','updatedDate'
        thread_text=row["mail_body"]
        #print(thread_subject)
        #location='location'    
        #input_data = create_payload('location',thread_text)      
        #create data
        for index,row in questions.iterrows():
            payload = create_payload(row["question"],thread_text) 
            #print(payload)
            if row["tag"] == 'location':
                location=call_endpoint(payload)
            elif row["tag"] == 'actiondate':
                actiondate=call_endpoint(payload)
            elif row["tag"] == 'poc':
                poc=call_endpoint(payload)
            elif row["tag"] == 'url':
                url=call_endpoint(payload)
            else:
                print( row["tag"] +":no action")    
        list_row = [id,title, 'description','event','','','',poc,url,actiondate,location,datetime.now(),'']      
        result_df.loc[len(result_df)]=list_row
    #print(result_df)
    result_df.to_json(s3_output_file_path,orient='records')      
    
    
def lambda_handler(event, context):
    
    #print("Received event: " + json.dumps(event, indent=2))      
    run_insight()
    answer={'status': 'insight_detection_completed',  'output_file_path': s3_output_file_path}
    resp = json.dumps(answer)
    resp = json.loads(resp)
    
    # TODO implement
    return {
        'statusCode': 200,
        'body': resp
    }
