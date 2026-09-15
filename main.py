import csv
import os

from sub_processes.ai_call import brief_ai_summary
from sub_processes.get_data import get_from_csv
from sub_processes.process_sponsor_data import sponsor_data
from sub_processes.process_submission_data import submissions_data
from sub_processes.process_user_data import user_data
from sub_processes.process_challenge_data import challenge_data
from sub_processes.postcode_geometry import postcode_coordinates


def run_processing(
    challenges_file,
    sponsors_file,
    users_file,
    submissions_file,
    output_directory,
    geodata_file=None,
    regional_geodata_file=None,
    memory_directory=None,
    mapping_reviewer=None,
    primary_ai_model=None,
    secondary_ai_model=None,
    finances_data=None,
):
    """Process selected source files and write all resultant CSV files."""
    if memory_directory is None:
        memory_directory = os.path.join(os.path.dirname(__file__), 'memory')

    os.makedirs(output_directory, exist_ok=True)
    os.makedirs(memory_directory, exist_ok=True)

    # Load data from CSV files
    users = get_from_csv(users_file)
    challenges = get_from_csv(challenges_file)
    sponsors = get_from_csv(sponsors_file)
    submissions = get_from_csv(submissions_file)

    #Process the data
    processed_users, ethnicity_table, ethnicity_join_table, submissions_join_table = user_data(
        users,
        memory_dir=memory_directory,
        mapping_reviewer=mapping_reviewer,
        primary_ai_model=primary_ai_model,
        secondary_ai_model=secondary_ai_model,
    )
    processed_submissions = submissions_data(submissions, processed_users)
    processed_challenges, reward_table = challenge_data(challenges)
    processed_sponsors = sponsor_data(sponsors)

    postcode_table = postcode_coordinates(
        geodata_file,
        memory_dir=memory_directory,
        regional_geodata_file=regional_geodata_file,
    )

    """print(brief_ai_summary(
        processed_users,
        processed_challenges,
        ethnicity_table,
        model=primary_ai_model,
    ))"""
    # Save the processed data to CSV files
    ethnicity_table.to_csv(os.path.join(output_directory, 'ethnicity_table.csv'), index=False)
    ethnicity_join_table.to_csv(os.path.join(output_directory, 'ethnicity_join_table.csv'), index=False)
    #submissions_join_table.to_csv(os.path.join(output_directory, 'submissions_join_table.csv'), index=False)
    processed_submissions.to_csv(os.path.join(output_directory, 'submissions_join_table.csv'), index=False)
    processed_users.to_csv(os.path.join(output_directory, 'processed_users.csv'), index=False)
    processed_challenges.to_csv(os.path.join(output_directory, 'processed_challenges.csv'), index=False)
    reward_table.to_csv(os.path.join(output_directory, 'reward_table.csv'), index=False)
    processed_sponsors.to_csv(os.path.join(output_directory, 'processed_sponsors.csv'), index=False)
    postcode_table.to_csv(os.path.join(output_directory, 'postcode_table.csv'), index=False)

    if finances_data is not None:
        with open(os.path.join(output_directory, 'finances.csv'), 'w', newline='') as finances_file:
            writer = csv.writer(finances_file)
            writer.writerow(['monthly_expenses', 'monthly_income', 'ytd_expenses', 'ytd_income'])
            writer.writerow([
                finances_data['monthly_expenses'],
                finances_data['monthly_income'],
                finances_data['ytd_expenses'],
                finances_data['ytd_income'],
            ])


def get_finances_data():
    """Prompt the user on the command line for the current financial information."""
    return {
        'monthly_expenses': input('Monthly expenses: ').strip(),
        'monthly_income': input('Monthly income: ').strip(),
        'ytd_expenses': input('YTD expenses: ').strip(),
        'ytd_income': input('YTD income: ').strip(),
    }


def main():
    cwd = os.getcwd()
    data_directory = os.path.join(cwd, 'data')
    run_processing(
        challenges_file=os.path.join(data_directory, 'challenges.csv'),
        sponsors_file=os.path.join(data_directory, 'sponsors.csv'),
        users_file=os.path.join(data_directory, 'users.csv'),
        output_directory=os.path.join(cwd, 'processed_data'),
        geodata_file=os.path.join(data_directory, 'open_nz_postcode_boundaries_shp.zip'),
        regional_geodata_file=os.path.join(data_directory, 'statsnz-regional-council-2025-clipped-SHP.zip'),
        memory_directory=os.path.join(cwd, 'memory'),
        finances_data=get_finances_data(),
    )

if __name__ == "__main__":
    main()

