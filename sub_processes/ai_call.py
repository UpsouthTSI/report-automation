import json
import pandas as pd
import os

DEFAULT_PRIMARY_MODEL = 'ollama:llama3.1:8b'
DEFAULT_SECONDARY_MODEL = 'ollama:deepseek-r1:7b'


def ai_call(prompt, model=DEFAULT_PRIMARY_MODEL):
    if model.split(':')[0] == 'ollama':
        return ai_call_ollama(prompt, model=model.split(':')[1])
    elif model.split(':')[0] == 'gpt':
        return ai_call_gpt(prompt, model=model.split(':')[1])
    elif model.split(':')[0] == 'gemini':
        return ai_call_gemini(prompt, model=model.split(':')[1])
    else:
        raise ValueError(f"Unsupported AI model: {model}")

def ai_call_ollama(prompt, model="llama3.1:8b"):
    import ollama
    response = ollama.chat(model=model, messages=
        [{"role": "user", "content": prompt}]
    )
    return response.message.content.strip().removeprefix("```json").removeprefix("```").removesuffix("```")

def ai_call_gpt(prompt, model="gpt-5"):
    from openai import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return response.output_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")

def ai_call_gemini(prompt, model="gemini-3.7-flash"):
    from google import genai
    client = genai.Client()
    response = client.interactions.create(
        model=model,
        input=prompt
    )
    return response.output_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")



def user_call_ai(prompt, categories, set_of_values, additions=[], primary_model=None, secondary_model=None):
    """
    Calls the AI model to map raw answers to categories.
    The answer is run through various checks to ensure it is valid JSON and contains all the raw answers. 

    Arguments:
    prompt: The prompt to send to the AI model
    categories: The list of categories to map the raw answers to
    set_of_values: The set of raw answers to map to the categories
    additions: Additional information to include in the prompt
    primary_model: Model that creates the initial mappings
    secondary_model: Model that verifies the initial mappings

    Returns:
    A dictionary mapping the raw answers to the categories


    """

    primary_model = primary_model or DEFAULT_PRIMARY_MODEL
    secondary_model = secondary_model or DEFAULT_SECONDARY_MODEL
    response = ai_call(
        prompt.format(categories=categories, set_of_values=set_of_values, additions='\n'.join(additions)),
        model=primary_model,
    )

    temp_prompt = prompt.format(categories=categories, set_of_values=set_of_values, additions='\n'.join(additions))

    secondary_prompt = f"""
        The following prompt was used to generate a mapping of raw answers to categories: 
        "{temp_prompt}"
        
        The following is the mapping of raw answers to categories: 
        {response}
        
        Please check the mapping above and ensure it is correct. If it is not correct, please return a corrected mapping.
        If the mapping is correct, please return the same mapping.
        Please reply with ONLY a valid JSON object like: {{"raw answer": "category", ...}}.
        Do not include any other text or explanation.
        """
    secondary_response = ai_call(secondary_prompt, model=secondary_model)

    #check if the response is valid JSON, if not, ask the AI to return valid JSON
    json_response = check_json_ai(secondary_response, model=secondary_model)
    
    #Drop any keys that are not in the set of values and any values that are not in the categories
    json_response = {k: v for k, v in json_response.items() if k in set_of_values and v in categories}

    # check if the response contains all the raw answers, if not, ask the AI to return all the raw answers
    if json_response.keys() != set_of_values:
        print("The AI response does not contain all the raw answers. Adding the missing raw answers")
        print(f"Difference between keys: {set_of_values - json_response.keys()}, {json_response.keys() - set_of_values}")
        difference = set_of_values - json_response.keys()
        user_call_result = user_call_ai(
            prompt,
            categories,
            difference,
            additions,
            primary_model=primary_model,
            secondary_model=secondary_model,
        )
        json_response.update(user_call_result)

    # pass the response to a secondary AI to double check the mapping and ensure it is correct, if not, ask the AI to return a corrected mapping

    # pass the response back to the user for review and allow them to make adjustments if needed
    print("Data Mapping Using AI:")
    for key, value in json_response.items():
        print(f"{key} -> {value}")

    #might need to do more cleaning of the response to ensure it's valid JSON, but for now we'll assume the AI returns valid JSON
    return json_response

def check_json_ai(response, model=None):
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        json_prompt = f"""
            The AI response was not valid JSON. Please check your response.
            
            Response: {response}
            
            Please reply with ONLY a valid JSON object like: {{"raw answer": "category", ...}}. 
            Do not include any other text or explanation.
            Please check your JSON is valid before replying.
            """
        response = ai_call(json_prompt, model=model)
        return check_json_ai(response, model=model)

def brief_ai_summary(users, challenges, sponsors, ethnicity_table, model=None):
    """
    Generates a brief summary of the data sets using an AI model.

    Args:
        users (DataFrame): The users data set.
        challenges (DataFrame): The challenges data set.
        sponsors (DataFrame): The sponsors data set.
        ethnicity_table (DataFrame): The ethnicity table data set.

    Returns:
        str: A brief summary of the data sets.
    """

    #get some basic information about the data set
    #get users that have signed up last calendar month, for below it is currently going from the current date but need to make it go from last calender month
    last_month_start = pd.Timestamp.now().replace(day=1) - pd.DateOffset(months=1)
    last_month_end = pd.Timestamp.now().replace(day=1)
    print(f"Last month start: {last_month_start}, Last month end: {last_month_end}")
    new_users = users[(pd.to_datetime(users['AccountCreatedAt'], errors='coerce', dayfirst=True) >= last_month_start)  & (pd.to_datetime(users['AccountCreatedAt'], errors='coerce', dayfirst=True) < last_month_end)]
    active_campaigns = challenges[(pd.to_datetime(challenges['ChallengeStartAt'], errors='coerce', dayfirst=True) < last_month_end) & (pd.to_datetime(challenges['ChallengeEndAt'], errors='coerce', dayfirst=True) >= last_month_start)]
    print(f"New users last month: {len(new_users)}, Active campaigns last month: {len(active_campaigns)}")
    print(active_campaigns[['ChallengeName', 'ChallengeStartAt', 'ChallengeEndAt']])
    
    print(challenges[(pd.to_datetime(challenges['ChallengeStartAt'], errors='coerce', dayfirst=True) < last_month_end)][['ChallengeName', 'ChallengeStartAt', 'ChallengeEndAt']])
    print(challenges[(pd.to_datetime(challenges['ChallengeEndAt'], errors='coerce', dayfirst=True) >= last_month_start)][['ChallengeName', 'ChallengeStartAt', 'ChallengeEndAt']])
    temp = pd.to_datetime(challenges[challenges['ChallengeId'] == 57]['ChallengeStartAt'], errors='coerce', dayfirst=True)
    print(temp, last_month_end, temp <= last_month_end)
    #provide some summary statistices
    prompt = f"""
        Please provide a brief summary of the following data sets:
        Users: {users}
        Challenges: {challenges}
        Sponsors: {sponsors}
        Ethnicity Table: {ethnicity_table}
        Active Challenges Last Month: {active_campaigns}
        
        Summary Statistics:
        - Time Period: {last_month_start.strftime('%Y-%m-%d')} to {last_month_end.strftime('%Y-%m-%d')}
        - New Users Last Month: {len(new_users)}
        - Active Challenges Last Month: {len(active_campaigns)}
        - Total Users: {len(users)}
        - Total Challenges: {len(challenges)}
        
        This summary is going along with a document of figures and tables, so it should be concise and highlight any important trends or insights in the last month.
        The summary should be written in a clear and concise manner, and should be suitable for a general audience.
        Please provide the summary in a single paragraph, and do not include any tables or figures in the summary.
        Ensure that any numbers or statistics are accurate and relevant to the data sets provided.
        Please only include the summary and do not include any other text or explanation.
    """
    response = ai_call(prompt, model=model or DEFAULT_PRIMARY_MODEL)
    return response