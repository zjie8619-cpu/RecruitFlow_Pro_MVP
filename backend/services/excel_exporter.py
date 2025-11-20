import pandas as pd
from pathlib import Path

def export_to_excel(df, output_path):
    """
    Export a pandas DataFrame to an Excel file.

    Args:
        df (pd.DataFrame): DataFrame to export.
        output_path (str or Path): Output file path.

    Returns:
        str: Full path of the generated file.
    """
    output_path = Path(output_path)

    # Ensure parent folder exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Export DataFrame
    df.to_excel(output_path, index=False, engine="openpyxl")

    return str(output_path)


def generate_ability_excel(df, filename="ability_sheet.xlsx"):
    """
    Generate an ability sheet Excel file under the /temp folder.

    Args:
        df (pd.DataFrame): DataFrame to write.
        filename (str): File name of the Excel file.

    Returns:
        str: Full path to the generated file.
    """
    temp_dir = Path("temp")
    temp_dir.mkdir(exist_ok=True)

    file_path = temp_dir / filename

    df.to_excel(file_path, index=False, engine="openpyxl")

    return str(file_path)
