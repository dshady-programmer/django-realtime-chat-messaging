ALLOWED_MIME_TYPES = [
    # Images
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/heic",

    # Audio / Voice notes
    "audio/mpeg",    # mp3
    "audio/mp4",     # m4a
    "audio/aac",
    "audio/ogg",
    "audio/wav",
    "audio/opus",

    # Video / Video notes
    "video/mp4",
    "video/quicktime",  # mov
    "video/webm",
    "video/ogg",
    "video/x-msvideo",  # avi
    "video/x-matroska", # mkv

    # Documents / Files
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document", # docx
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",       # xlsx
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",# pptx
    "text/plain",
    "text/csv",
]


MEDIATYPE_CHOICES = [
    ("image", "Image"),
    ("video", "Video"),  # includes video notes 
    ("audio", "Audio"),  # includes voice notes
    ("file", "File"),
]

NOTIFICATION_TYPE = (
    ('REACTION', 'Reaction'),
    ('NEW_MESSAGE', 'New Message'),
    ('REPLY', 'Reply')
)