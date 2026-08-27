import os

from sub_processes.ai_call import brief_ai_summary
from sub_processes.get_data import get_from_csv
from sub_processes.process_sponsor_data import sponsor_data
from sub_processes.process_user_data import user_data
from sub_processes.process_challenge_data import challenge_data
from sub_processes.postcode_geometry import postcode_coordinates


def main():

    cwd = os.getcwd()
    data_directory = os.path.join(cwd, 'data')
    processed_data_directory = os.path.join(cwd, 'processed_data')
    memory_directory = os.path.join(cwd, 'memory')
    geodata_file = os.path.join(data_directory, 'open_nz_postcode_boundaries_shp.zip')

    # Load data from CSV files
    users = get_from_csv(os.path.join(data_directory, 'users.csv'))
    challenges = get_from_csv(os.path.join(data_directory, 'challenges.csv'))
    sponsors = get_from_csv(os.path.join(data_directory, 'sponsors.csv'))

    #Process the data
    processed_users, ethnicity_table, ethnicity_join_table, submissions_join_table = user_data(users, memory_dir=memory_directory)
    processed_challenges, reward_table = challenge_data(challenges)
    processed_sponsors = sponsor_data(sponsors)

    postcode_table = postcode_coordinates(geodata_file, memory_dir=memory_directory)

    print(brief_ai_summary(processed_users, processed_challenges, processed_sponsors, ethnicity_table))
    # Save the processed data to CSV files
    ethnicity_table.to_csv(os.path.join(processed_data_directory, 'ethnicity_table.csv'), index=True)
    ethnicity_join_table.to_csv(os.path.join(processed_data_directory, 'ethnicity_join_table.csv'), index=False)
    submissions_join_table.to_csv(os.path.join(processed_data_directory, 'submissions_join_table.csv'), index=False)
    processed_users.to_csv(os.path.join(processed_data_directory, 'processed_users.csv'), index=False)
    processed_challenges.to_csv(os.path.join(processed_data_directory, 'processed_challenges.csv'), index=False)
    reward_table.to_csv(os.path.join(processed_data_directory, 'reward_table.csv'), index=False)
    processed_sponsors.to_csv(os.path.join(processed_data_directory, 'processed_sponsors.csv'), index=False)
    postcode_table.to_csv(os.path.join(processed_data_directory, 'postcode_table.csv'), index=False)

if __name__ == "__main__":
    main()

