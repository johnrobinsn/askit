import os

path = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(path, 'files')
if not os.path.exists(path):
    os.makedirs(path)

async def list_files() -> str:
    """
    Lists the files that are available.

    Returns:
        str: A list of files in the given directory.
    """
    import os

    try:
        files = os.listdir(path)
        if len(files) == 0:
            return f"No files available"
        else:
            return f"Files available: {', '.join(files)}"
    except Exception as e:
        return f"An error occurred: {e}"
    

async def write_file(filename: str, content: str) -> str:
    """
    Writes the given content to a file with the given filename.

    Args:
        filename (str): The name of the file to write to.
        content (str): The content to write to the file.

    Returns:
        str: A message indicating whether the write was successful.
    """
    try:
        with open(os.path.join(path, filename), 'w') as f:
            f.write(content)
        return f"Successfully wrote to {filename}"
    except Exception as e:
        return f"An error occurred: {e}"
    
async def read_file(filename: str) -> str:
    """
    Reads the content of a file with the given filename.

    Args:
        filename (str): The name of the file to read.

    Returns:
        str: The content of the file, or an error message if the read fails.
    """
    try:
        with open(os.path.join(path, filename), 'r') as f:
            return f.read()
    except Exception as e:
        return f"An error occurred: {e}"

def register():
    return [list_files, write_file, read_file]
    
