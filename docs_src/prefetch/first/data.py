user = await User.query.create(name="Edgy")

for i in range(5):
    await Post.query.create(comment="Comment number %s" % i, user=user)

for i in range(50):
    await Article.query.create(content="Comment number %s" % i, user=user)

ravyn = await User.query.create(name="Ravyn")

for i in range(15):
    await Post.query.create(comment="Comment number %s" % i, user=ravyn)

for i in range(20):
    await Article.query.create(content="Comment number %s" % i, user=ravyn)
