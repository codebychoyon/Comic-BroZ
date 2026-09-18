from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from .forms import RegisterForm, LoginForm, PasswordChangeForm, UserUpdateForm, ProfileUpdateForm
from .models import User, Movie, Comic, Blog, Comment, Like, Profile, WatchHistory, Testimonial, CharacterCard, Category
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q
from dashboard.forms import BlogForm
from django.views.decorators.http import require_POST
import stripe
import bleach
from payments.models import Order
from django.db.models import Q, F
from .utils import fetch_movie_from_tmdb

stripe.api_key = settings.STRIPE_SECRET_KEY

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password']
            )
            messages.success(request, 'Registration successful! Please login.')
            return redirect('login')
    else:
        form = RegisterForm()
    return render(request, 'register.html', {'form': form})

def login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, email=email, password=password)
            if user is not None:
                auth_login(request, user)
                messages.success(request, 'Login successful!')
                
                # Redirect based on user type
                if user.is_staff or user.is_superuser:
                    return redirect('admin_dashboard')  # You can create this url
                else:
                    return redirect('home')  # You can create this url
            else:
                messages.error(request, 'Invalid credentials')
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})

@login_required
def logout(request):
    auth_logout(request)
    messages.success(request, 'Logged out successfully!')
    return redirect('login')

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Your password was successfully updated! Please login again.')
            auth_logout(request)
            return redirect('login')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordChangeForm(user=request.user)
    return render(request, 'change_password.html', {'form': form})


def home(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    blogs = Blog.objects.all().order_by('-created_at')[:3]
    comics = Comic.objects.all().order_by('-created_at')[:6]
    testimonials = Testimonial.objects.all()
    print("Testimonials:", list(testimonials))  # For debugging
    return render(request, 'home.html', {
        'username': request.user.username,
        'blogs': blogs,
        'comics': comics,
        'testimonials': testimonials
    })

def movies(request):
    movies = Movie.objects.all()
    return render(request, 'movies.html', {'movies': movies})

# def movie_detail(request, pk):
#     movie = get_object_or_404(Movie, pk=pk)
#     return render(request, 'movie_detail.html', {'movie': movie})

def about(request):
    return render(request, 'about.html')


def comic(request):
    comics = Comic.objects.all().order_by('-created_at')
    return render(request, 'comics.html', {'comics': comics})

def comic_detail(request, pk):
    comic = get_object_or_404(Comic, id=pk)
    return render(request, 'comic_detail.html', {
        'comic': comic,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY
    })

@login_required
def comic_read(request, pk):
    comic = get_object_or_404(Comic, id=pk)
    is_preview = request.user not in comic.purchased_by.all()
    return render(request, 'comic_read.html', {
        'comic': comic,
        'is_preview': is_preview,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY
    })

stripe.api_key = settings.STRIPE_SECRET_KEY
YOUR_DOMAIN = 'https://comic-broz.onrender.com'  # Update to production domain later

@login_required
def comic_purchase(request, pk):
    comic = get_object_or_404(Comic, pk=pk)
    if request.method == 'POST':
        try:
            if not comic.price or comic.price <= 0:
                return JsonResponse({'error': 'Invalid comic price'}, status=400)

            order = Order.objects.create(
                user=request.user,
                comic=comic,
                amount=comic.price
            )

            image_url = None
            if comic.image and comic.image.url:
                image_url = request.build_absolute_uri(comic.image.url)

            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': comic.title or 'Untitled Comic',
                            'description': (comic.description[:200] if comic.description else 'No description'),
                            'images': [image_url] if image_url else [],
                        },
                        'unit_amount': int(comic.price * 100),
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=YOUR_DOMAIN + f'/comics/success-page/{order.id}/',  # Match with success_page URL
                cancel_url=YOUR_DOMAIN + f'/comics/{pk}/',
                metadata={'order_id': str(order.id)}  # Ensure order_id is a string
            )

            print("Success URL:", YOUR_DOMAIN + f'/comics/success-page/{order.id}/')
            order.stripe_payment_intent = session.payment_intent
            order.save()
            return JsonResponse({'id': session.id})

        except stripe.error.StripeError as e:
            order.delete()
            return JsonResponse({'error': f'Stripe error: {str(e)}'}, status=400)
        except Exception as e:
            order.delete()
            return JsonResponse({'error': f'Server error: {str(e)}'}, status=400)
    return redirect('comic_detail', pk=pk)

@login_required
def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    print("Order has_paid:", order.has_paid)  # Debug
    if order.has_paid:
        return redirect('success_page', order_id=order.id)
    return redirect('comic_detail', pk=order.comic.pk)

def success_page(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'success.html', {'order': order})

@login_required
def comic_favorite(request, pk):
    comic = get_object_or_404(Comic, pk=pk)
    if request.method == 'POST':
        if request.user in comic.favorited_by.all():
            messages.warning(request, "This comic is already in your favorites.")
            return JsonResponse({'success': False, 'message': "This comic is already in your favorites."})
        else:
            comic.favorited_by.add(request.user)
            messages.success(request, f"Added {comic.title} to favorites!")
            return JsonResponse({'success': True, 'message': f"Added {comic.title} to favorites!"})
    return redirect('comic_detail', pk=pk)

@login_required
def comic_unfavorite(request, pk):
    comic = get_object_or_404(Comic, pk=pk)
    if request.method == 'POST':
        if request.user not in comic.favorited_by.all():
            messages.warning(request, "This comic is not in your favorites.")
            return JsonResponse({'success': False, 'message': "This comic is not in your favorites."})
        else:
            comic.favorited_by.remove(request.user)
            messages.success(request, f"Removed {comic.title} from favorites!")
            return JsonResponse({'success': True, 'message': f"Removed {comic.title} from favorites!"})
    return redirect('comic_detail', pk=pk)

# @login_required
# def comic_read(request, pk):
#     comic = get_object_or_404(Comic, pk=pk)
#     if request.user not in comic.purchased_by.all():
#         messages.error(request, "You must purchase this comic to read it.")
#         if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#             return JsonResponse({'success': False, 'message': "You must purchase this comic to read it."})
#     else:
#         if request.user not in comic.read_by.all():
#             comic.read_by.add(request.user)
#             messages.success(request, f"You have read {comic.title}!")
#             if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#                 return JsonResponse({'success': True, 'message': f"You have read {comic.title}!"})
#         messages.info(request, f"Reading {comic.title}.")  # Placeholder
#         if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#             return JsonResponse({'success': True, 'message': f"Reading {comic.title}."})
#     return redirect('comic_detail', pk=pk)


@login_required
def profile_view(request):
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=request.user)

    comics_purchased = request.user.purchased_comics.count()
    comics_read = request.user.read_comics.count()
    comics_favorited = request.user.favorited_comics.count()
    # Annotate favorite comics with delays
    favorite_comics = [
        {'comic': comic, 'delay': index * 100}
        for index, comic in enumerate(request.user.favorited_comics.order_by('-id')[:3])
    ]

    watch_history = WatchHistory.objects.filter(user=request.user).select_related('movie')
    movies_watched = watch_history.count()
    hours_streamed = sum(history.movie.runtime for history in watch_history) / 60 if watch_history else 0
    recently_watched = watch_history.order_by('-watched_at').first()

    blogs_written = request.user.blogs_written.count()
    blogs_liked = Like.objects.filter(user=request.user).count()
    comments_posted = Comment.objects.filter(user=request.user, user__isnull=False).count()

    total_activity = comics_purchased + comics_read + comics_favorited + movies_watched + blogs_written + blogs_liked + comments_posted
    max_activities = 100
    progress = min(int((total_activity / max_activities) * 100), 100)

    if progress <= 33:
        level = "Sidekick"
    elif progress <= 66:
        level = "Hero"
    else:
        level = "Superhero"

    profile.progress = progress
    profile.level = level
    profile.save()

    context = {
        'profile': profile,
        'comics_purchased': comics_purchased,
        'comics_read': comics_read,
        'comics_favorited': comics_favorited,
        'favorite_comics': favorite_comics,
        'movies_watched': movies_watched,
        'hours_streamed': round(hours_streamed, 1),
        'recently_watched': recently_watched,
        'blogs_written': blogs_written,
        'blogs_liked': blogs_liked,
        'comments_posted': comments_posted,
    }
    return render(request, 'profile.html', context)


def blog(request):
    blogs = Blog.objects.all().order_by('-created_at')
    
    # Identify featured blog (the absolute latest one)
    featured_blog = blogs.first() if blogs.exists() else None
    
    # Identify popular blogs (top 3 by views)
    popular_blogs = Blog.objects.order_by('-views_count')[:3]
    
    # Search
    search_query = request.GET.get('q')
    if search_query:
        blogs = blogs.filter(Q(title__icontains=search_query) | Q(content__icontains=search_query))
        featured_blog = None # Hide featured block when searching
        
    # Category Filter
    category_id = request.GET.get('category')
    if category_id:
        blogs = blogs.filter(category_id=category_id)
        featured_blog = None # Hide featured block when filtering
        
    # Remove featured blog from the main feed if it's being displayed
    if featured_blog:
        blogs = blogs.exclude(id=featured_blog.id)
        
    # Pagination
    paginator = Paginator(blogs, 6) # 6 blogs per page in a 2-column layout fits nicely
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    categories = Category.objects.all()
    
    return render(request, 'blogs.html', {
        'page_obj': page_obj, 
        'categories': categories, 
        'search_query': search_query,
        'current_category': int(category_id) if category_id else None,
        'featured_blog': featured_blog,
        'popular_blogs': popular_blogs,
    })

@login_required
def create_blog(request):
    if request.method == 'POST':
        form = BlogForm(request.POST, request.FILES)
        if form.is_valid():
            blog = form.save(commit=False)
            blog.author = request.user
            blog.save()
            # messages.success(request, 'Your blog has been posted successfully!')
            return redirect('blogs')
    else:
        form = BlogForm()
    return render(request, 'create_blog.html', {'form': form})

@login_required
@require_POST
def edit_blog(request, blog_id):
    blog = get_object_or_404(Blog, id=blog_id)
    if blog.author != request.user:
        return JsonResponse({'success': False, 'message': 'You are not authorized to edit this blog.'}, status=403)
    
    form = BlogForm(request.POST, request.FILES, instance=blog)
    if form.is_valid():
        blog = form.save()
        return JsonResponse({
            'success': True,
            'message': 'Blog updated successfully!',
            'blog': {
                'id': blog.id,
                'title': blog.title,
                'content': blog.content,
                'image': blog.image.url if blog.image else ''
            }
        })
    else:
        return JsonResponse({'success': False, 'message': 'Error updating blog. Please check the form.'}, status=400)

@login_required
@require_POST
def delete_blog(request, blog_id):
    blog = get_object_or_404(Blog, id=blog_id)
    if blog.author != request.user:
        # messages.error(request, 'You are not authorized to delete this blog.')
        return redirect('blogs')
    
    try:
        blog.delete()
        messages.success(request, 'Blog deleted successfully!')
    except Exception as e:
        messages.error(request, f'Error deleting blog: {str(e)}')
    return redirect('blogs')

def blog_detail(request, blog_id):
    blog = get_object_or_404(Blog, id=blog_id)
    
    # Increment view count
    blog.views_count += 1
    blog.save()
    
    # Calculate read time
    word_count = len(blog.content.split())
    read_time = max(1, round(word_count / 200)) # 200 WPM average
    
    comments = blog.comments.filter(parent__isnull=True).prefetch_related('replies')
    recent_blogs = Blog.objects.exclude(id=blog_id)[:5]
    likes_count = Like.objects.filter(blog=blog).count()
    user_liked = False
    if request.user.is_authenticated:
        user_liked = Like.objects.filter(blog=blog, user=request.user).exists()

    context = {
        'blog': blog,
        'comments': comments,
        'recent_blogs': recent_blogs,
        'likes_count': likes_count,
        'user_liked': user_liked,
        'read_time': read_time,
    }
    return render(request, 'blog_details.html', context)

@login_required
def like_blog(request, blog_id):
    blog = get_object_or_404(Blog, id=blog_id)
    user = request.user

    if request.method == 'POST':
        liked = Like.objects.filter(blog=blog, user=user).exists()
        if liked:
            Like.objects.filter(blog=blog, user=user).delete()
            liked = False
        else:
            Like.objects.create(blog=blog, user=user)
            liked = True

        likes_count = blog.likes.count()
        return JsonResponse({
            'success': True,
            'liked': liked,
            'likes_count': likes_count
        })
    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)

@login_required
def add_comment(request, blog_id):
    blog = get_object_or_404(Blog, id=blog_id)
    if request.method == 'POST':
        content = request.POST.get('content')
        parent_id = request.POST.get('parent_id')
        if not content:
            return JsonResponse({'success': False, 'message': 'Content is required'})
        
        comment_kwargs = {
            'blog': blog,
            'user': request.user,
            'content': content,
        }
        if parent_id:
            parent = get_object_or_404(Comment, id=parent_id)
            if parent.replies.count() >= 50:
                return JsonResponse({'success': False, 'message': 'Maximum 50 replies reached'})
            comment_kwargs['parent'] = parent
        
        comment = Comment.objects.create(**comment_kwargs)
        
        return JsonResponse({
            'success': True,
            'comment_id': comment.id,
            'content': comment.content,
            'user_username': comment.user.username,
            'user_avatar': comment.user.profile.profile_image.url if hasattr(comment.user, 'profile') and comment.user.profile.profile_image else None,
            'created_at': comment.created_at.strftime('%B %d, %Y %H:%M'),
            'comments_count': blog.comments.count(),
        })
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@login_required
def edit_comment(request, blog_id, comment_id):
    blog = get_object_or_404(Blog, id=blog_id)
    comment = get_object_or_404(Comment, id=comment_id, blog=blog)
    
    if not comment.user or comment.user != request.user:
        return JsonResponse({'success': False, 'message': 'You are not authorized to edit this comment'}, status=403)
    
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            try:
                comment.content = bleach.clean(content, tags=['p', 'b', 'i', 'u', 'strong', 'em'], strip=True)
                comment.save()
                return JsonResponse({
                    'success': True,
                    'comment_id': comment.id,
                    'content': comment.content,
                    'message': 'Comment updated successfully'
                })
            except Exception as e:
                return JsonResponse({'success': False, 'message': f'Error updating comment: {str(e)}'}, status=500)
        return JsonResponse({'success': False, 'message': 'Comment content cannot be empty'}, status=400)
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)

@login_required
def delete_comment(request, blog_id, comment_id):
    blog = get_object_or_404(Blog, id=blog_id)
    comment = get_object_or_404(Comment, id=comment_id, blog=blog)
    
    if not comment.user or comment.user != request.user:
        return JsonResponse({'success': False, 'message': 'You are not authorized to delete this comment'}, status=403)
    
    if request.method == 'POST':
        try:
            comment.delete()
            return JsonResponse({
                'success': True,
                'comments_count': blog.comments.count(),
                'message': 'Comment deleted successfully'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error deleting comment: {str(e)}'}, status=500)
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=400)

def contact(request):
    return render(request, 'contact.html')

@login_required
def profile_update(request):
    user = request.user
    profile = user.profile
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            return redirect('profile')
    else:
        u_form = UserUpdateForm(instance=user)
        p_form = ProfileUpdateForm(instance=profile)
    return render(request, 'profile_update.html', {'u_form': u_form, 'p_form': p_form})


def character_card(request):
    # Get all characters
    characters = CharacterCard.objects.all()

    # Handle search
    search_query = request.GET.get('search', '')
    if search_query:
        characters = characters.filter(name__icontains=search_query)

    # Handle sorting
    sort_option = request.GET.get('sort', '')
    if sort_option == 'name_asc':
        characters = characters.order_by('name')
    elif sort_option == 'name_desc':
        characters = characters.order_by('-name')
    elif sort_option == 'rating_desc':
        # Calculate total rating as the sum of attributes
        characters = characters.annotate(
            total_rating=F('special_powers') + F('cunning') + F('strength') + F('technology')
        ).order_by('-total_rating')
    elif sort_option == 'debut_year_desc':
        characters = characters.order_by('-debut_year')

    context = {
        'characters': characters,
        'search_query': search_query,
    }
    return render(request, 'characters_card_list.html', context)


def search_movie(request):
    query = request.GET.get('q', '').strip()
    print("Query received:", query)
    movie = None
    error = None
    if query:
        print("Fetching movie for:", query)
        movie = fetch_movie_from_tmdb(query)
        print("Movie fetched:", movie)
        if not movie:
            error = f"No movie found for '{query}'. Try 'Iron Man' instead of 'Ironman'."
            print("Error:", error)
    else:
        error = "Please enter a movie title to search."
    
    # Order movies by last_searched, newest first
    movies = Movie.objects.all().order_by('-last_searched')
    print("All movies:", [(m.title, m.last_searched) for m in movies])
    return render(request, 'movies.html', {'movie': movie, 'movies': movies, 'query': query, 'error': error})