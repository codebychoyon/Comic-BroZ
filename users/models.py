from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify

class UserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email field must be set'))
        if not username:
            raise ValueError(_('The Username field must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, username, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):  
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    is_staff = models.BooleanField(default=False) 
    is_active = models.BooleanField(default=True) 
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.username
    
    
class Movie(models.Model):
    title = models.CharField(max_length=255)
    release_date = models.DateField()
    runtime = models.PositiveIntegerField(help_text="Runtime in minutes")
    image = models.ImageField(upload_to='movies/images/', blank=True, null=True)
    description = models.TextField()
    watch_link = models.URLField(max_length=255, blank=True, null=True)
    last_searched = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class WatchHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='watch_history')
    movie = models.ForeignKey('Movie', on_delete=models.CASCADE, related_name='watched_by')
    watched_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} watched {self.movie.title} on {self.watched_at}"
    
class Comic(models.Model):
    title = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='comic_images/', blank=True, null=True)
    description = models.TextField(blank=True)
    purchased_by = models.ManyToManyField(User, related_name='purchased_comics', blank=True)
    read_by = models.ManyToManyField(User, related_name='read_comics', blank=True)
    favorited_by = models.ManyToManyField(User, related_name='favorited_comics', blank=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)

    def __str__(self):
        return self.title
    
class ComicPage(models.Model):
    comic = models.ForeignKey(Comic, related_name='pages', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='comic_pages/')
    page_number = models.PositiveIntegerField()

    class Meta:
        ordering = ['page_number']

    def __str__(self):
        return f"{self.comic.title} - Page {self.page_number}"

    
    
class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comic_favorites')
    comic = models.ForeignKey(Comic, on_delete=models.CASCADE, related_name='favorites')
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)

    class Meta:
        unique_together = ('user', 'comic')

    def __str__(self):
        return f"{self.user.username} favorited {self.comic.title}" 

class Purchase(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comic_purchases')
    comic = models.ForeignKey('Comic', on_delete=models.CASCADE, related_name='purchases')
    purchased_at = models.DateTimeField(auto_now_add=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = ('user', 'comic')

    def __str__(self):
        return f"{self.user.username} purchased {self.comic.title} on {self.purchased_at}"  
    
class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Blog(models.Model):
    STATUS_CHOICES = [("draft", "Draft"), ("published", "Published")]
    
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True, null=True)
    excerpt = models.CharField(max_length=300, blank=True)
    content = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='blogs')
    image = models.ImageField(upload_to='blog_images/', blank=True, null=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blogs_written', blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    views_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)  

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            # handle duplicate slugs if needed, simple version for now
            original_slug = self.slug
            queryset = Blog.objects.exclude(pk=self.pk)
            counter = 1
            while queryset.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
    
class Like(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    blog = models.ForeignKey(Blog, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'blog')

    def __str__(self):
        return f"{self.user.username} liked {self.blog.title}"
    
class Comment(models.Model):
    blog = models.ForeignKey(Blog, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_comments')
    content = models.TextField()
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Comment by {self.user.username} on {self.blog.title}"

    class Meta:
        ordering = ['created_at']

class PostDislike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_dislikes')
    blog = models.ForeignKey(Blog, on_delete=models.CASCADE, related_name='dislikes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'blog')

    def __str__(self):
        return f"{self.user.username} disliked {self.blog.title}"

class CommentLike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comment_likes')
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'comment')

    def __str__(self):
        return f"{self.user.username} liked comment {self.comment.id}"

class CommentDislike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comment_dislikes')
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='dislikes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'comment')

    def __str__(self):
        return f"{self.user.username} disliked comment {self.comment.id}"
    
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_image = models.ImageField(upload_to='profile_images/', default="200.png", blank=True, null=True)
    favorite_quote = models.TextField(blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    level = models.CharField(max_length=50, default="Sidekick")
    progress = models.PositiveIntegerField(default=0)  # Progress as a percentage (0-100)

    def __str__(self):
        return f"{self.user.username}'s Profile"
    

class Testimonial(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    content = models.TextField()
    image = models.ImageField(upload_to='testimonials/', default='default.jpg')
    role = models.CharField(max_length=100, default="Reader")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Testimonial by {self.author}"
    

class CharacterCard(models.Model):
    name = models.CharField(max_length=100)  # Character's name (e.g., "Super-Bro")
    title = models.CharField(max_length=100)  # Character's title (e.g., "The Amazing")
    debut_year = models.IntegerField()  # Debut year (e.g., 2023)
    special_powers = models.IntegerField()  # Special powers score (out of 50)
    cunning = models.IntegerField()  # Cunning score (out of 50)
    strength = models.IntegerField()  # Strength score (out of 50)
    technology = models.IntegerField()  # Technology score (out of 50)
    fact_file = models.TextField()  # Fact file description
    image = models.ImageField(upload_to='CharacterCard/', default="200.png", blank=True, null=True)  # URL to character image (optional)
    back_content = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name