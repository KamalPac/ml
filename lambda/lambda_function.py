import boto3
import json
import pandas as pd
import s3fs
import re
from datetime import datetime


client = boto3.client('sagemaker-runtime')

endpoint_name = "insight-bert-2023-11-13-20-40-49-689"                                      
content_type = "application/list-text"  # The MIME type of the input data in the request body.
accept = "application/json" 
s3_input_file_path1 ='s3://abb8-ml-model/dailydownload/mailContents.json'
s3_input_file_path ='./mailContents.json'
s3_output_file_bucket ='s3://abb8-ml-model/summarization/insights.json'
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
    
def process_files(s3_input_file_path):
    docs = pd.read_json(s3_input_file_path1)
    docs.insert(3,"insight_dates","")
    docs.insert(4,"summary","")
    return docs
    #print(docs.head(1))
    #print(questions.head(1))

def clean_text(raw_text):
    preprocessed_text = raw_text.strip().replace('\n','')
    preprocessed_text = re.sub('[^a-zA-Z0-9//.:]', ' ', raw_text.lower())
    preprocessed_text = re.sub('\s+', ' ', preprocessed_text)
    return preprocessed_text
    
#function to call T5 model
def query_endpoint_and_parse_response(payload_dict, endpoint_name):
    encoded_json = json.dumps(payload_dict).encode("utf-8")
    client = boto3.client("runtime.sagemaker")
    response = client.invoke_endpoint(
        EndpointName=endpoint_name, ContentType="application/json", Body=encoded_json
    )
    model_predictions = json.loads(response["Body"].read())
    return model_predictions["generated_texts"]  

#function to call T5 model
def get_summary(preprocessed_text, endpoint_name):
    prompt_template = "Write a short summary for this text: {text}"
    parameters = {
        "max_length": 200,
        "num_return_sequences": 1,
        "top_k": 100,
        "top_p": .95,
        "do_sample": True,
        "early_stopping": False,
        "num_beams": 1,
        "no_repeat_ngram_size": 3,
        "temperature": 1
    }

    payload = {"text_inputs": prompt_template.replace("{text}", preprocessed_text), **parameters}
    generated_texts = query_endpoint_and_parse_response(payload, endpoint_name)
    #print(f"For prompt: '{prompts}'")
    #print(f"Result: {generated_texts}")   
    return generated_texts    
    
def run_insight(s3_input_file_path):
    docs= process_files(s3_input_file_path)
    questions=pd.read_csv(s3_prompt_questions_path)
    df = pd.DataFrame(columns=['thread_id','text', 'label'])
    result_df= pd.DataFrame(columns=['id','title', 'description','type','status','documents','pocID','poc','url','actionDate','location','createdDate','updatedDate'])
    for index,row in docs.iterrows():
        id=row["thread_id"]
        title=row["mail_subject"]
       
        #'type','status','documents','pocID','poc','url','actionDate','location','createdDate','updatedDate'
        thread_text=clean_text(row["mail_body"])
        description=get_summary(thread_text,'insight-summary')
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
        list_row = [id,title, description,'event','','','',poc,url,actiondate,location,datetime.now(),'']      
        result_df.loc[len(result_df)]=list_row
    #print(result_df)
    filename= s3_input_file_path[s3_input_file_path.rindex('/')+1:]
    s3_output_file_path=f's3://abb8-ml-model/summarization/insights_{filename}'
    result_df.to_json(s3_output_file_path,orient='records')      

   
    
def lambda_handler(event, context):
    
    #print("Received event: " + json.dumps(event, indent=2))   
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']
    filepath=f's3://abb8-ml-model/{key}'
    print(filepath)
    run_insight(filepath)
    
    answer={'status': 'insight_detection_completed',  'output_file_path': s3_output_file_path}
    resp = json.dumps(answer)
    resp = json.loads(resp)
    
    # TODO implement
    return {
        'statusCode': 200,
        'body': resp
    }
