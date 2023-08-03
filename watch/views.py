from django.shortcuts import render
from django.views.generic import DetailView, ListView
from live.models import Stream


class WatchStream(DetailView):
    model = Stream
    queryset = Stream.objects
    template_name = "watch.html"


class ListStreams(ListView):
    model = Stream
    queryset = Stream.objects
    template_name = "list.html"
