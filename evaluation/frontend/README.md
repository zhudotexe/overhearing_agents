# Passive Agents Eval Frontend

This is a very simple frontend to help with labelling model suggestions.

Pretty much all the business logic is controlled by the server.py file, not here.

```shell
# install deps
$ npm i
# run dev version
$ npm run dev
# build for deployment (so that server.py will serve the static files)
$ npm run build
```

See `package.json` for other npmscripts.

DEV NOTE:
I kind of abuse TypeScript here since I'm not strongly typing any API returns but I can't be asked because the deadline
is in 3 weeks :(
