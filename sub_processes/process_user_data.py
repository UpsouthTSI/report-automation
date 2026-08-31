import json
import os
import re
import pandas as pd
from sub_processes.ai_call import user_call_ai

def user_data(data, memory_dir=None, mapping_reviewer=None):
    #set the UserPostcode column to int type and handling Nans
    data = process_postcode(data)
    #Check the data for any issues
    if not check_data(data):
        raise ValueError("Data validation failed. Please check the data for issues.")
    # Remove identifiable information from the data
    data = remove_identifiable_info(data)
    # Process the 'DOB' column in the data
    data = process_DOB(data)
    # Process the 'Ethnicity' column in the data
    ethnicity_table, ethnicity_join_table = get_ethnicity(
        data,
        memory_dir=memory_dir,
        mapping_reviewer=mapping_reviewer,
    )
    # Process the 'Submissions' column in the data
    submissions_join_table = process_submissions(data)
    # Process the 'Gender' column in the data
    data = process_gender(data, memory_dir=memory_dir, mapping_reviewer=mapping_reviewer)
    return data, ethnicity_table, ethnicity_join_table, submissions_join_table

def process_DOB(data):
    """
    Process the 'DOB' column in the given DataFrame.

    Args:
        data (pd.DataFrame): The user data containing a 'DOB' column.    
    Returns:    
        pd.DataFrame: The user data with an additional 'Processed_DOB' column.
    """
    print(data['DateOfBirth'])
    # Convert the 'DOB' column to datetime format
    data['Processed_DOB'] = pd.to_datetime(data['DateOfBirth'], errors='coerce', format='%d/%m/%Y', dayfirst=True)

    # Check for any invalid dates and set them to NaT (Not a Time)
    data.loc[data['Processed_DOB'].isna(), 'Processed_DOB'] = pd.NaT

    return data


def get_ethnicity(data, memory_dir=None, mapping_reviewer=None):
    """
    Process the 'Ethnicity' column in the given DataFrame.

    Args:
        data (pd.DataFrame): The user data containing an 'Ethnicity' column.    
    Returns:
        pd.DataFrame: The user data with an additional 'Processed_Ethnicity' column.
    """

    unique_data = data['Ethnicity'].unique()
    set_of_ethnicities = set()
    for ethnicity in unique_data:
        specific_ethnicities = process_specific_ethnicity(ethnicity)
        set_of_ethnicities.update(specific_ethnicities)

    categories = ['New Zealand European', 'Māori', 'Pacifica', 'Asian', 'Middle Eastern', 'Latin American', 'African', 'Other', 'Unknown']

    old_mappings = {}

    # Get old mappings
    if memory_dir and 'ethnicity_mapping.json' in os.listdir(memory_dir):
        with open(os.path.join(memory_dir, 'ethnicity_mapping.json'), 'r') as f:
            old_mappings = json.load(f)

    #select the values that need to be mapped
    value_to_create_mappings = set_of_ethnicities - set(old_mappings.keys())
    if len(value_to_create_mappings):
        prompt = """
            Match each raw survey answer below to the correct category.
            Some answers have misspellings or may be a subset of another category (e.g. "New Zeland european" = "New Zealand European", "Dutch" = "European").
            Treat "Unknown" as its own category for missing/blank answers.
            {additions}

            Categories: {categories}

            Raw answers: {set_of_values}

            Only use the categories provided above. Do not create new categories.
            Reply with ONLY a JSON object like: {{"raw answer": "category", ...}}.
            Do not include any other text or explanation.
            Please check your JSON is valid before replying.
        """
        # Use AI to map the new values
        values = user_call_ai(prompt, categories, value_to_create_mappings)

        if mapping_reviewer:
            values = mapping_reviewer('Ethnicity', values, categories)
            if values is None:
                raise RuntimeError('Processing cancelled while reviewing new ethnicity mappings.')

        # Update old mappings with reviewed new values
        old_mappings.update(values)

    # Save updated mappings
        if memory_dir:
            with open(os.path.join(memory_dir, 'ethnicity_mapping.json'), 'w') as f:
                json.dump(old_mappings, f, indent=4)


    ethnicity_table = pd.DataFrame(columns=['Category', 'Specific Ethnicity'])

    for key, value in old_mappings.items():
        ethnicity_table = pd.concat([ethnicity_table, pd.DataFrame({'Category': [value], 'Specific Ethnicity': [key]})], ignore_index=True)

    ethnicity_join_table = pd.DataFrame(columns=['UserID', 'EthnicityID'])

    for index, row in data.iterrows():
        user_id = row['UserID']
        ethnicity = row['Ethnicity']
        specific_ethnicities = process_specific_ethnicity(ethnicity)
        for specific_ethnicity in specific_ethnicities:
            if specific_ethnicity in old_mappings:
                index = ethnicity_table[ethnicity_table['Specific Ethnicity'] == old_mappings[specific_ethnicity]].index.start
                ethnicity_join_table = pd.concat([ethnicity_join_table, pd.DataFrame({'UserID': [user_id], 'EthnicityID': [index]})], ignore_index=True)

    return ethnicity_table, ethnicity_join_table

def process_specific_ethnicity(ethnicity):
    if pd.isna(ethnicity):
        return ['Unknown']
    elif ';' in ethnicity:
        split_ethnicities = [e.strip() for e in ethnicity.split(';')]
        temp_ethnicities = []
        for e in split_ethnicities:
            value = process_specific_ethnicity(e)
            temp_ethnicities.extend(value)
        return temp_ethnicities
    elif '/' in ethnicity:
        split_ethnicities = [e.strip() for e in ethnicity.split('/')]
        temp_ethnicities = []
        for e in split_ethnicities:
            value = process_specific_ethnicity(e)
            temp_ethnicities.extend(value)
        return temp_ethnicities
    elif '&' in ethnicity:
        split_ethnicities = [e.strip() for e in ethnicity.split('&')]
        temp_ethnicities = []
        for e in split_ethnicities:
            value = process_specific_ethnicity(e)
            temp_ethnicities.extend(value)
        return temp_ethnicities
    else:
        if ":" in ethnicity:
            ethnicity = ethnicity.split(":")[1].strip()
        return [ethnicity.strip().title()]



def process_gender(data, memory_dir=None, mapping_reviewer=None):
    """
    Process the 'Gender' column in the given DataFrame.

    Args:
        data (pd.DataFrame): The user data containing a 'Gender' column.
        memory_dir (str, optional): Directory to store and retrieve gender mappings. Defaults to None.

    Returns:
        pd.DataFrame: The user data with an additional 'Processed_Gender' column.
    """
    # Normalize the 'Gender' column to lowercase and strip whitespace
    data['Gender'] = data['Gender'].replace(r'[^a-zA-Z\s]', '', regex=True)  # Remove any non-alphabetic characters
    data['Gender'] = data['Gender'].str.lower().str.strip()

    #Replace nans with 'Unknown'
    data['Gender'] = data['Gender'].fillna('Unknown')

    # Get unique values in the 'Gender' column
    unique_genders = data['Gender'].unique()

    # Define the categorys
    categories = ['Male', 'Female', 'Non-binary', 'Prefer not to say', 'Other', 'Unknown']

    # Initialize an empty dictionary to store old mappings
    old_mappings = {}

    # Get old mappings
    if memory_dir and 'gender_mapping.json' in os.listdir(memory_dir):
        with open(os.path.join(memory_dir, 'gender_mapping.json'), 'r') as f:
            old_mappings = json.load(f)

    #select the values that need to be mapped
    value_to_create_mappings = set(unique_genders) - set(old_mappings.keys())
    if len(value_to_create_mappings):
        prompt = """
            Match each raw survey answer below to the correct category.
            Some answers have misspellings or different wording (e.g. "femele" = Female, "woman" = Female).
            Treat "Unknown" as its own category for missing/blank answers.
            {additions}

            Categories: {categories}

            Raw answers: {set_of_values}

            Reply with ONLY a JSON object like: {{"raw answer": "category", ...}}. 
            Do not include any other text or explanation.
            Please check your JSON is valid before replying.
        """

        # Use AI to map the new values
        values = user_call_ai(prompt, categories, value_to_create_mappings)

        if mapping_reviewer:
            values = mapping_reviewer('Gender', values, categories)
            if values is None:
                raise RuntimeError('Processing cancelled while reviewing new gender mappings.')

        # Update old mappings with reviewed new values
        old_mappings.update(values)

    # Save updated mappings
        if memory_dir:
            with open(os.path.join(memory_dir, 'gender_mapping.json'), 'w') as f:
                json.dump(old_mappings, f, indent=4)

    # Map the 'Gender' column using the updated mappings and fill NaN values with 'Unknown'
    data['Processed_Gender'] = data['Gender'].map(old_mappings).fillna('Unknown')

    return data

def remove_identifiable_info(data):
    """
    Remove identifiable information from the DataFrame.

    Args:
        data (pd.DataFrame): The user data containing identifiable information.

    Returns:
        pd.DataFrame: The user data with identifiable information removed.
    """
    # Add code to remove identifiable information from the DataFrame
    data = data.drop(columns=['Username', 'Email', 'FirstName', 'LastName', 'UserBio'])

    # looking for emails and phone numbers in any other columns and removing them
    for column in data.columns:
        data[column] = data[column].astype(str).str.replace(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', regex=True)  # Remove emails
        data[column] = data[column].astype(str).str.replace(r'\b\d{10}\b', '', regex=True)  # Remove phone numbers (10 digits)

    return data

def process_submissions(data):
    """
    Process the 'Submissions' column in the given DataFrame.

    Args:
        data (pd.DataFrame): The user data containing a 'Submissions' column.   
    
    Returns:
        pd.DataFrame: The user data with an additional 'Processed_Submissions' column.
    """

    submissions_join_table = pd.DataFrame(columns=['UserID', 'SubmissionID'])

    for index, row in data.iterrows():
        user_id = row['UserID']
        submissions = row['SubmissionIds']
        if pd.isna(submissions):
            continue
        submission_list = [s.strip() for s in submissions.split(',')]
        for submission in submission_list:
            submissions_join_table = pd.concat([submissions_join_table, pd.DataFrame({'UserID': [user_id], 'SubmissionID': [submission]})], ignore_index=True)

    return submissions_join_table

def process_postcode(data):
    """
    Process the 'UserPostcode' column in the given DataFrame.

    Args:
        data (pd.DataFrame): The user data containing a 'UserPostcode' column.

    Returns:
        pd.DataFrame: The user data with the 'UserPostcode' column processed.
    """
    # Set the 'UserPostcode' column to Int64 type to handle NaN values
    data['UserPostcode'] = data['UserPostcode'].astype('string')
    # Remove ".0" from the end of the postcode if it exists
    data['UserPostcode'] = data['UserPostcode'].str.replace(r'\.0$', '', regex=True)
    # Remove any whitespace from the postcode
    data['UserPostcode'] = data['UserPostcode'].str.strip()

    # Use regex to check if the Postcode column contains valid NZ postcodes (4 digits) or no postcode (NaN)
    if not data['UserPostcode'].map(lambda x: re.match(r'^\d{4}$|<NA>$', str(x).strip()) is not None).all():
        print("Invalid Postcodes found.")
        # Show the invalid postcodes
        for index, row in data.iterrows():
            postcode = row['UserPostcode']
            if not re.match(r'^\d{4}$|<NA>$', str(postcode).strip()):
                if re.match(r'^\d{3}$', str(postcode).strip()):
                    #padd with a leading zero
                    data.loc[index, 'UserPostcode'] = '0' + str(postcode).strip()
                else:
                    print(f"Invalid Postcode: {postcode} at index {index}")
                    data.loc[index, 'UserPostcode'] = pd.NA

    return data

def check_data(data):
    """
    Check the data for any issues.

    Args:
        data (pd.DataFrame): The user data to check.

    Returns:
        bool: True if the data is valid, False otherwise.
    """
    if data['UserID'].duplicated().any():
        print("Duplicate UserIDs found.")
        return False

    return True