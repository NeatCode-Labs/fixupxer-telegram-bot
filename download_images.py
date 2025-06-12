import requests
import os

# URLs from the screenshot
before_url = "https://before" # Replace with actual URL
after_url = "https://after"   # Replace with actual URL

# Download the images
def download_image(url, filename):
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            print(f"Successfully downloaded {filename}")
        else:
            print(f"Failed to download {filename}. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error downloading {filename}: {e}")

# Download the images if they don't already exist
if not os.path.exists("Before"):
    download_image(before_url, "Before")
else:
    print("Before image already exists")

if not os.path.exists("After"):
    download_image(after_url, "After")
else:
    print("After image already exists")

print("Done!") 