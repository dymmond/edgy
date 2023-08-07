# This assumes you have the models imported
# or accessible from somewhere allowing you to generate
# these records in your database

acme = await Organisation.query.create(ident="ACME Ltd")
red_team = await Team.query.create(org=acme, name="Red Team")
blue_team = await Team.query.create(org=acme, name="Blue Team")
green_team = await Team.query.create(org=acme, name="Green Team")

await Member.query.create(team=red_team, email="charlie@redteam.com")
await Member.query.create(team=red_team, email="brown@redteam.com")
await Member.query.create(team=blue_team, email="snoopy@blueteam.com")
monica = await Member.query.create(team=green_team, email="monica@blueteam.com")

# New data
user = await User.query.create(member=monica, name="Saffier")
profile = await Profile.query.create(user=user, profile_type="admin")
