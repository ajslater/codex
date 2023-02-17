# Django Channel Customizations

## Why Channels?

I use only a small portion of django channels' functionality and it would take
much less code to only copy their lovely `utils.await_many_dispatch()` function
for a custom websocket application to await connections and the broadcast queue.

However, `channels.auth.AuthMiddlewareStack` is nice and complex so I've
customized Channels instead.

## Thread Leaks

I've failed close ThreadExecutors from each consumer so a custom thread cleanup
function using private python thread methods runs at the end of the
codex.application.lifespan application. This will cease functioning if python
stops exposing thread locks on the threads.
