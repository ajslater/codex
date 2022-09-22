# Codex Frontend

The codex frontend runs on [VueJS](https://vuejs.org/) and
[Vuetify](https://vuetifyjs.com).

## Development

See the package.json file for common development scripts. Running the live
reloading dev server is your best bet.

## Production

The Django collectstatic script packages the vite rolled up modules from
`codex/static_build/` and packages them with the main server app in
`codex/static_root/`.
