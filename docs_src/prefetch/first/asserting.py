assert len(users) == 2  # Total ussers

edgy = [value for value in users if value.pk == edgy.pk][0]
assert len(edgy.to_posts) == 5  # Total posts for Edgy
assert len(edgy.to_articles) == 50  # Total articles for Edgy

esmerald = [value for value in users if value.pk == esmerald.pk][0]
assert len(esmerald.to_posts) == 15  # Total posts for Esmerald
assert len(esmerald.to_articles) == 20  # Total articles for Esmerald
