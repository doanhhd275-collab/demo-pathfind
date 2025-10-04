# Start from an official, lightweight Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy all your project files into the container
COPY . .

# Install the Python libraries listed in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Command to run when the container starts
# The host 0.0.0.0 is important to make it accessible from outside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]