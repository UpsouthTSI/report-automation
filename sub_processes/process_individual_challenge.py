import os
from sub_processes.get_data import get_from_csv
from sub_processes.process_user_data import process_gender

def process_from_beginning(challenge_file, output_dir, memory_dir=None, mapping_reviewer=None, primary_ai_model=None, secondary_ai_model=None):
    if memory_dir is None:
        memory_dir = os.path.join(os.getcwd(), 'memory')

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(memory_dir, exist_ok=True)
    challenge_data = get_from_csv(challenge_file)
    challenge_data = process_individual_challenge(challenge_data, memory_dir=memory_dir, mapping_reviewer=mapping_reviewer, primary_ai_model=primary_ai_model, secondary_ai_model=secondary_ai_model)
    challenge_data.to_csv(os.path.join(output_dir, os.path.basename(challenge_file)), index=False)

def process_individual_challenge(challenge_data, memory_dir=None, mapping_reviewer=None, primary_ai_model=None, secondary_ai_model=None):
    challenge_data = remove_identifiable_information(challenge_data)
    challenge_data = process_gender(challenge_data, memory_dir=memory_dir, mapping_reviewer=mapping_reviewer, primary_ai_model=primary_ai_model, secondary_ai_model=secondary_ai_model)
    return challenge_data

def remove_identifiable_information(challenge_data):
    # Implement the logic to remove identifiable information from the challenge data
    # For example, you might remove names, email addresses, or other personal identifiers
    return challenge_data