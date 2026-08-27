import pandas as pd


def get_from_csv(filename):
    """
    Get data from a CSV file.

    Args:
        filename (str): The path to the CSV file.

    Returns:
        pd.DataFrame: The data from the CSV file.
    """
    if filename.endswith('.csv'):
        data = pd.read_csv(filename)
        return data
    else:
        filename = input('File must be .csv')
        return get_from_csv(filename)



