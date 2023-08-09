import httpx

data = {
    "name": "Edgy",
    "email": "edgy@esmerald.dev",
    "language": "EN",
    "description": "A description",
}

# Make the API call to create the user with some posts
# This will also create the posts and associate them with the user
# All the posts will be in uppercase as per `field_validator` in the ModelRef.
response = httpx.post("/create", json=data)
