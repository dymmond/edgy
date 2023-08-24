# Create the album
album = await Album.query.create(name="Malibu")

# Create the track
await Track.query.create(album=album, title="The Bird", position=1)

# Create the studio
studio = await Studio.query.create(album=album, name="Valentim")

# Create the company
await Company.query.create(studio=studio)
