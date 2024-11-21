# Package Locks

## eslint

It seems like eslint 9.15 introduced a change that breask
typescrupt/eslint-plugin
<https://github.com/typescript-eslint/typescript-eslint/issues/10338> This was
fixed in @typescript-eslint/plugin 8.15

However, it looks like sonarj & probably unicorn at the very least rely on
typescript-eslint/plugin 7.x

So I must pin eslint to 9.14 until this issue is resolved in dependenant plugins
