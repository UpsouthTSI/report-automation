import matplotlib.pyplot as plt
import pandas as pd
import re



def executive_performance_overview_figs():
    # Total Campaigns
    # Total Signups
    # New monthly signups
    # Active Campaigns
    # Reward_money from last month
    # Available reward money from last month
    # Number of submissions last month
    pass

def users_figs(users, submission_join_table):
    #Number of users over the last two years by month (Submitting users, Number of users, Website visitors)
    user_data = pd.to_datetime(users['AccountCreatedAt'], errors='coerce', dayfirst=True)
    user_data = user_data.dt.to_period('M').value_counts().sort_index()

    join_table = users.merge(submission_join_table, how='inner', left_on='UserID', right_on='UserId')
    #remove duplicate user ids
    join_table['AccountCreatedAt_dt'] = pd.to_datetime(join_table['AccountCreatedAt'], errors='coerce', dayfirst=True)
    join_table['AccountCreatedAt_period'] = join_table['AccountCreatedAt_dt'].dt.to_period('M')
    submission_month_count = join_table.groupby('AccountCreatedAt_period').UserID.nunique()
    print(submission_month_count)

    # Check if submissions id has digit using regex
    alt_count = users[users['SubmissionIds'].apply(lambda x: bool(re.search(r'\d', str(x))))]
    alt_count = pd.to_datetime(alt_count['AccountCreatedAt'], errors='coerce', dayfirst=True)
    alt_count = alt_count.groupby(alt_count.dt.to_period('M')).size()

    
    #join submission data with user data
    #Add in submitting users
    x = range(len(user_data))  # Example: last two years by month (24 months)
    plt.figure(figsize=(10, 6))
    plt.plot(user_data.index.astype(str), user_data.values, label='Users')
    plt.plot(submission_month_count.index.astype(str), submission_month_count.values, label='Submitting Users')
    plt.plot(alt_count.index.astype(str), alt_count.values, label='Alt Submitting Users')
    plt.xticks(rotation=45)
    plt.xlabel('Month')
    plt.ylabel('Number of Users')
    plt.title('Number of Users Over the Last Two Years by Month')
    plt.legend()
    plt.savefig('users_over_time.png')
    plt.close()
