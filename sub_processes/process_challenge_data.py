import pandas as pd
import re

def challenge_data(data):
    """
    Processes the challenge data by performing necessary transformations and cleaning.

    Args:
        data (pd.DataFrame): The challenge data to be processed.

    Returns:
        pd.DataFrame: The processed challenge data.
    """
    # Example processing: extract reward descriptions into a separate table
    reward_table = process_reward_description(data)
    return data, reward_table

def process_reward_description(data):
    """
    Processes the 'RewardDescription' column in the challenge data to extract reward tiers and their details.

    Args:
        data (pd.DataFrame): The challenge data containing the 'RewardDescription' column.

    Returns:
        pd.DataFrame: A DataFrame containing the extracted reward tiers and their details.
    """
    reward_table = pd.DataFrame(columns=['ChallengeID', 'Tier', 'Name', 'Value', 'Amount'])

    for index, row in data.iterrows():
        challenge_id = row['ChallengeId']
        reward_tiers = row['RewardDescription']
        """
        RewardDescriptions Template:
        Reward Tier 1: Name = Power Idea, Value = 100, Total = 2 | Reward Tier 2: Name = Awesome Idea, Value = 5, Total = 100
        Each reward tier is separated by a pipe (|) and each attribute of a tier is separated by a comma (,). The attributes of each reward are separated by an equals sign (=).
        """
        if pd.isna(reward_tiers):
            continue
        for tier in reward_tiers.split('|'):
            tier = tier.strip()
            if not tier:
                continue
            tier_parts = tier.split(',')
            tier_name = re.findall(r'Reward Tier (\d+)', tier_parts[0])[0] if len(tier_parts) > 0 else ''
            reward_name = tier_parts[0].split('=')[1].strip() if len(tier_parts) > 0 and '=' in tier_parts[0] else ''
            reward_value = tier_parts[1].split('=')[1].strip() if len(tier_parts) > 1 and '=' in tier_parts[1] else ''
            reward_amount = tier_parts[2].split('=')[1].strip() if len(tier_parts) > 2 and '=' in tier_parts[2] else ''

            reward_table = pd.concat([reward_table, pd.DataFrame({
                'ChallengeID': [challenge_id],
                'Tier': [tier_name],
                'Name': [reward_name],
                'Value': [reward_value],
                'Amount': [reward_amount]
            })], ignore_index=True)

    return reward_table