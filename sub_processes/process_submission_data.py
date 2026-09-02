


def submissions_data(data, users):

    # Remove identifiable data
    data = remove_identifiable_info(data)

    # Check data connected to users
    data = check_data_connected_to_users(data, users)

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
    data = data.drop(columns=['UserName', 'UserEmail', 'FirstName', 'LastName', 'Ethnicity', 'Gender', 'UserPostcode', 'SubmissionTitle', 'SubmissionBody', 'VideoId', 'VideoThumbnailUrl', 'VideoHLSUrl', 'VideoMP4Url', 'PublicImageUrl', 'PublicAudioUrl', 'PublicDocumentUrl'])

    # looking for emails and phone numbers in any other columns and removing them
    for column in data.columns:
        data[column] = data[column].astype(str).str.replace(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', regex=True)  # Remove emails
        data[column] = data[column].astype(str).str.replace(r'\b\d{10}\b', '', regex=True)  # Remove phone numbers (10 digits)

    return data

def check_data_connected_to_users(data, users):
    """
    Check if the data is connected to the users.

    Args:
        data (pd.DataFrame): The user submission data.
        users (pd.DataFrame): The user information data.

    Returns:
        pd.DataFrame: The user submission data with only entries connected to users.
    """
    # join the data with users on 'UserId'
    number_that_do_not_match = len(data) - len(data.merge(users, left_on='UserId', right_on='UserID', how='inner'))
    if number_that_do_not_match > 0:
        print(f"Number of submissions not connected to users: {number_that_do_not_match}, removing these records.")
    temp_data = data.merge(users, left_on='UserId', right_on='UserID', how='inner')
    matching_DOB = temp_data[temp_data['DateOfBirth_x'] == temp_data['DateOfBirth_y']]
    number_without_matching_DOB = len(temp_data) - len(matching_DOB)
    if number_without_matching_DOB > 0:
        print(temp_data[~(temp_data['DateOfBirth_x'] != temp_data['DateOfBirth_y'])][['SubmissionId', 'UserId', 'DateOfBirth_x', 'DateOfBirth_y']])
        print(f"Number of submissions without matching Date of Birth to the user records: {number_without_matching_DOB}, removing these records.")
    return data[data['SubmissionId'].isin(matching_DOB['SubmissionId'])]
