import os

version = os.environ["VERSION"]
tag = os.environ["TAG"]
environment = os.environ["ENVIRONMENT"]

print("================================")
print("Release Build Information")
print("================================")
print(f"Version:     {version}")
print(f"Tag:         {tag}")
print(f"Environment: {environment}")
print("================================")
