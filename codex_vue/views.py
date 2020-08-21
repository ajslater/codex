from django.shortcuts import render


def app(request):
    return render(request, "codex_vue/index.html")
