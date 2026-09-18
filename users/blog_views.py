from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.db.models import Q

from .models import Blog, Like, Category, PostDislike, CommentLike, CommentDislike, Comment

class BlogListView(ListView):
    model = Blog
    template_name = 'blog/blog_list.html'
    context_object_name = 'blogs'
    paginate_by = 18

    def get_queryset(self):
        queryset = super().get_queryset().filter(status='published').order_by('-created_at')
        
        # Handling Search
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) | Q(content__icontains=search_query)
            )
            
        # Handling Category filter
        category_slug = self.request.GET.get('category', '')
        if category_slug:
            queryset = queryset.filter(category__name__iexact=category_slug)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context

class BlogDetailView(DetailView):
    model = Blog
    template_name = 'blog/blog_detail.html'
    context_object_name = 'blog'
    
    def get_object(self, queryset=None):
        blog = super().get_object(queryset)
        blog.views_count += 1
        blog.save(update_fields=['views_count'])
        return blog

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['recent_blogs'] = Blog.objects.filter(status='published').exclude(id=self.object.id).order_by('-created_at')[:9]
        if self.request.user.is_authenticated:
            context['user_liked'] = Like.objects.filter(blog=self.object, user=self.request.user).exists()
            context['user_disliked'] = PostDislike.objects.filter(blog=self.object, user=self.request.user).exists()
            context['user_comment_likes'] = list(CommentLike.objects.filter(user=self.request.user, comment__blog=self.object).values_list('comment_id', flat=True))
            context['user_comment_dislikes'] = list(CommentDislike.objects.filter(user=self.request.user, comment__blog=self.object).values_list('comment_id', flat=True))
        else:
            context['user_liked'] = False
            context['user_disliked'] = False
            context['user_comment_likes'] = []
            context['user_comment_dislikes'] = []
        return context

class BlogCreateView(LoginRequiredMixin, CreateView):
    model = Blog
    template_name = 'blog/blog_form.html'
    fields = ['title', 'category', 'image', 'excerpt', 'content', 'status']

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('blog_detail', kwargs={'slug': self.object.slug})

class BlogUpdateView(LoginRequiredMixin, UpdateView):
    model = Blog
    template_name = 'blog/blog_form.html'
    fields = ['title', 'category', 'image', 'excerpt', 'content', 'status']

    def get_queryset(self):
        return super().get_queryset().filter(author=self.request.user)
        
    def get_success_url(self):
        return reverse_lazy('blog_detail', kwargs={'slug': self.object.slug})

class ToggleLikeView(LoginRequiredMixin, View):
    def post(self, request, slug, *args, **kwargs):
        blog = get_object_or_404(Blog, slug=slug)
        liked = Like.objects.filter(blog=blog, user=request.user).exists()
        if liked:
            Like.objects.filter(blog=blog, user=request.user).delete()
            liked = False
        else:
            Like.objects.create(blog=blog, user=request.user)
            # Remove dislike if it exists
            PostDislike.objects.filter(blog=blog, user=request.user).delete()
            liked = True
        return JsonResponse({'liked': liked, 'likes_count': blog.likes.count(), 'dislikes_count': blog.dislikes.count()})

class TogglePostDislikeView(LoginRequiredMixin, View):
    def post(self, request, slug, *args, **kwargs):
        blog = get_object_or_404(Blog, slug=slug)
        disliked = PostDislike.objects.filter(blog=blog, user=request.user).exists()
        if disliked:
            PostDislike.objects.filter(blog=blog, user=request.user).delete()
            disliked = False
        else:
            PostDislike.objects.create(blog=blog, user=request.user)
            # Remove like if it exists
            Like.objects.filter(blog=blog, user=request.user).delete()
            disliked = True
        return JsonResponse({'disliked': disliked, 'dislikes_count': blog.dislikes.count(), 'likes_count': blog.likes.count()})

class ToggleCommentLikeView(LoginRequiredMixin, View):
    def post(self, request, comment_id, *args, **kwargs):
        comment = get_object_or_404(Comment, id=comment_id)
        liked = CommentLike.objects.filter(comment=comment, user=request.user).exists()
        if liked:
            CommentLike.objects.filter(comment=comment, user=request.user).delete()
            liked = False
        else:
            CommentLike.objects.create(comment=comment, user=request.user)
            # Remove dislike if it exists
            CommentDislike.objects.filter(comment=comment, user=request.user).delete()
            liked = True
        return JsonResponse({'liked': liked, 'likes_count': comment.likes.count(), 'dislikes_count': comment.dislikes.count()})

class ToggleCommentDislikeView(LoginRequiredMixin, View):
    def post(self, request, comment_id, *args, **kwargs):
        comment = get_object_or_404(Comment, id=comment_id)
        disliked = CommentDislike.objects.filter(comment=comment, user=request.user).exists()
        if disliked:
            CommentDislike.objects.filter(comment=comment, user=request.user).delete()
            disliked = False
        else:
            CommentDislike.objects.create(comment=comment, user=request.user)
            # Remove like if it exists
            CommentLike.objects.filter(comment=comment, user=request.user).delete()
            disliked = True
        return JsonResponse({'disliked': disliked, 'dislikes_count': comment.dislikes.count(), 'likes_count': comment.likes.count()})
