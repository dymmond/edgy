assert len(users) == 2  # Total ussers

edgy = [value for value in users if value.pk == edgy.pk][0]
assert len(edgy.to_posts) == 5  # Total posts for Edgy
assert len(edgy.to_articles) == 50  # Total articles for Edgy

ravyn = [value for value in users if value.pk == ravyn.pk][0]
assert len(ravyn.to_posts) == 15  # Total posts for Ravyn
assert len(ravyn.to_articles) == 20  # Total articles for Ravyn
