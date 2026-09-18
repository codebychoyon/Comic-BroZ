from django import forms
from users.models import Blog, Comic, Like, Comment

class BlogForm(forms.ModelForm):
    class Meta:
        model = Blog
        fields = ['title', 'category', 'content', 'image']  # Exclude 'author' field


class ComicForm(forms.ModelForm):
    class Meta:
        model = Comic
        fields = ['title', 'description', 'price', 'image']

class LikeForm(forms.ModelForm):
    class Meta:
        model = Like
        fields = ['user', 'blog']

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']


# class UserForm(forms.ModelForm):
#     class Meta:
#         model = User
#         fields = ['username']