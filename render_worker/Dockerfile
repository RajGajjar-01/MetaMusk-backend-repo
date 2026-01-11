FROM manimcommunity/manim:v0.18.0

USER root

# Install additional LaTeX packages and ffmpeg for video processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    texlive-latex-extra \
    texlive-fonts-extra \
    texlive-science \
    dvipng \
    cm-super \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Create output directories with proper permissions
# Manim needs these directories for rendering
RUN mkdir -p /app/output && chmod 777 /app/output
RUN mkdir -p /app/output/Tex && chmod 777 /app/output/Tex
RUN mkdir -p /app/output/videos && chmod 777 /app/output/videos
RUN mkdir -p /app/output/images && chmod 777 /app/output/images

# Set Manim media directory environment variable
ENV MEDIA_DIR=/app/output

# Expose port
EXPOSE 8080

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
