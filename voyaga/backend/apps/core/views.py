from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from datetime import timedelta

from .models import User, OTPCode, AuditLog, Notification
from .serializers import RegisterSerializer, LoginSerializer, UserSerializer, ReviewSerializer
from apps.bookings.models import Review


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            AuditLog.log(user, "register", request=request)
            return Response({"user": UserSerializer(user).data, "tokens": {"access": str(refresh.access_token), "refresh": str(refresh)}}, status=201)
        return Response(serializer.errors, status=400)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            refresh = RefreshToken.for_user(user)
            AuditLog.log(user, "login", request=request)
            return Response({"user": UserSerializer(user).data, "tokens": {"access": str(refresh.access_token), "refresh": str(refresh)}})
        return Response(serializer.errors, status=400)


class VerifyOTPView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        code = request.data.get("code")
        if not code:
            return Response({"error": "OTP code required"}, status=400)
        expiry = timezone.now() - timedelta(minutes=10)
        otp = OTPCode.objects.filter(user=request.user, code=code, is_used=False, created_at__gte=expiry).first()
        if not otp:
            return Response({"error": "Invalid or expired OTP"}, status=400)
        otp.is_used = True
        otp.save()
        request.user.is_verified = True
        request.user.save()
        return Response({"message": "Email verified successfully"})


class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        return Response(UserSerializer(request.user).data)
    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


class ReviewListCreateView(generics.ListCreateAPIView):
    serializer_class = ReviewSerializer
    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]
    def get_queryset(self):
        qs = Review.objects.select_related("reviewer").order_by("-created_at")
        prop_id = self.request.query_params.get("property") or self.request.query_params.get("prop")
        if prop_id:
            qs = qs.filter(prop_id=prop_id)
        return qs
    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class AIChatView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        message = request.data.get("message", "").strip()
        history = request.data.get("history", [])
        if not message:
            return Response({"error": "Message required"}, status=400)
        context = self._build_full_context(request.user)
        try:
            reply = self._claude_reply(message, history, request.user, context)
            return Response({"reply": reply})
        except Exception:
            pass
        reply = self._smart_reply(message.lower(), request.user, context)
        return Response({"reply": reply})

    def _build_full_context(self, user):
        from apps.properties.models import Property
        from apps.bookings.models import Booking, Review as ReviewModel, Wishlist
        ctx = {}

        props = Property.objects.filter(is_active=True).prefetch_related("images", "reviews").select_related("host")
        prop_lines = []
        prop_index = {}
        for p in props:
            avg = p.avg_rating
            reviews = list(p.reviews.all())
            amenity_str = ", ".join(p.amenities) if p.amenities else "none listed"
            line = (
                "ID:" + str(p.id) + " | " + p.title + " | " + p.property_type.upper() + " | " +
                p.city + ", " + p.country + " | $" + str(p.price_per_night) + "/night | " +
                "max " + str(p.max_guests) + " guests | " + str(p.bedrooms) + "bd " + str(p.bathrooms) + "ba | " +
                "Rating: " + (str(avg) if avg else "No reviews yet") + " (" + str(len(reviews)) + " reviews) | " +
                "Amenities: " + amenity_str + " | " +
                "Host: " + (p.host.get_full_name() or p.host.username) + " | " +
                "Desc: " + (p.description or "")[:120]
            )
            prop_lines.append(line)
            prop_index[p.id] = {
                "title": p.title, "city": p.city, "country": p.country,
                "price": float(p.price_per_night), "type": p.property_type,
                "guests": p.max_guests, "beds": p.bedrooms, "baths": p.bathrooms,
                "rating": avg, "amenities": p.amenities or [],
                "description": p.description or "",
                "host": p.host.get_full_name() or p.host.username,
                "review_count": len(reviews),
            }
        ctx["prop_lines"] = prop_lines
        ctx["prop_index"] = prop_index
        ctx["prop_count"] = len(prop_lines)

        all_reviews = ReviewModel.objects.select_related("prop", "reviewer").order_by("-created_at")
        review_lines = []
        for r in all_reviews:
            name = r.reviewer.get_full_name().strip() or r.reviewer.username
            review_lines.append("[" + r.prop.title + "] " + name + " - " + str(r.rating) + " stars - " + r.comment)
        ctx["review_lines"] = review_lines
        ctx["review_count"] = len(review_lines)

        ctx["stats"] = {
            "users": User.objects.count(),
            "hosts": User.objects.filter(role="host").count(),
            "bookings": Booking.objects.filter(status__in=["confirmed", "completed"]).count(),
            "active_props": ctx["prop_count"],
        }

        user_bookings = Booking.objects.filter(guest=user).select_related("listing").order_by("-created_at")
        user_booking_lines = []
        for b in user_bookings:
            user_booking_lines.append(
                b.listing.title + " in " + b.listing.city + " | " +
                str(b.check_in) + " to " + str(b.check_out) + " | $" +
                str(b.total_price) + " | Status: " + b.status
            )
        try:
            wishlist_names = [w.property.title for w in Wishlist.objects.filter(user=user).select_related("property")]
        except Exception:
            wishlist_names = []
        reviewed_props = [r.prop.title for r in ReviewModel.objects.filter(reviewer=user).select_related("prop")]

        ctx["user"] = {
            "name": user.get_full_name().strip() or user.username,
            "email": user.email,
            "role": user.role,
            "tier": getattr(user, "loyalty_tier", "Explorer"),
            "points": getattr(user, "loyalty_points", 0) or 0,
            "discount": getattr(user, "loyalty_discount", 0) or 0,
            "wallet": float(user.wallet_balance),
            "bookings": user_booking_lines,
            "booking_count": len(user_booking_lines),
            "wishlist": wishlist_names,
            "reviewed": reviewed_props,
            "joined": user.date_joined.strftime("%B %Y"),
        }
        return ctx

    def _claude_reply(self, message, history, user, ctx):
        import anthropic
        u = ctx["user"]
        pts = u["points"]
        stats = ctx["stats"]
        props_txt = "\n".join(ctx["prop_lines"]) if ctx["prop_lines"] else "No active listings yet."
        rev_txt = "\n".join(ctx["review_lines"][:40]) if ctx["review_lines"] else "No reviews yet."

        if pts < 500:
            next_tier = "Silver (need " + str(500 - pts) + " more points for 5% off)"
        elif pts < 2000:
            next_tier = "Gold (need " + str(2000 - pts) + " more points for 7% off)"
        elif pts < 5000:
            next_tier = "Platinum (need " + str(5000 - pts) + " more points for 10% off)"
        else:
            next_tier = "Already at Platinum - maximum tier!"

        booking_history = "\n".join(u["bookings"]) if u["bookings"] else "No bookings yet"
        wishlist_txt = ", ".join(u["wishlist"]) if u["wishlist"] else "Empty"
        reviewed_txt = ", ".join(u["reviewed"]) if u["reviewed"] else "None yet"

        system_parts = [
            "You are Voya, the brilliant AI travel concierge for Voyaga - a luxury crypto travel platform.",
            "You have COMPLETE real-time database access. Answer every question with full specific detail. Never say you do not have information.",
            "",
            "=== VOYAGA COMPANY ===",
            "Built by Team Voyaga(DE). Mission: borderless, transparent, conscious travel.",
            "Support: help@voyaga.com (24hr response). Tech: Django REST + Vanilla JS + SQLite.",
            "",
            "=== PAYMENTS ===",
            "Cryptos accepted: BTC, ETH, USDT, SOL, LTC, BNB, DOGE. Zero fees for guests and hosts.",
            "Host payout: 97% INSTANTLY on booking confirmation (not checkout). Platform keeps 3%.",
            "Cancellation: 100% full refund instantly. Host payout auto-reversed.",
            "",
            "=== LOYALTY PROGRAM ===",
            "Earn 1 point per $1 spent. Points NEVER expire.",
            "Explorer (0pts) -> Silver (500pts, 5% off) -> Gold (2000pts, 7% off) -> Platinum (5000pts, 10% off)",
            "Current user: " + u["tier"] + " tier, " + str(pts) + " points, " + str(u["discount"]) + "% discount. Next: " + next_tier,
            "",
            "=== PLATFORM STATS (LIVE) ===",
            "Users: " + str(stats["users"]) + " | Hosts: " + str(stats["hosts"]) + " | Active listings: " + str(stats["active_props"]) + " | Confirmed bookings: " + str(stats["bookings"]) + " | Reviews: " + str(ctx["review_count"]),
            "",
            "=== ALL ACTIVE PROPERTIES (LIVE DATABASE) ===",
            props_txt,
            "",
            "=== ALL GUEST REVIEWS (LIVE DATABASE) ===",
            rev_txt,
            "",
            "=== CURRENT USER PROFILE ===",
            "Name: " + u["name"] + " | Email: " + u["email"] + " | Role: " + u["role"] + " | Joined: " + u["joined"],
            "Tier: " + u["tier"] + " (" + str(pts) + " pts, " + str(u["discount"]) + "% off) | Wallet: $" + str(round(u["wallet"], 2)),
            "Next milestone: " + next_tier,
            "Wishlist: " + wishlist_txt,
            "Reviewed properties: " + reviewed_txt,
            "Bookings (" + str(u["booking_count"]) + "):",
            booking_history,
            "",
            "=== HOW TO RESPOND ===",
            "Use **bold** and emojis. Keep under 280 words but be specific and detailed.",
            "For property searches: list ALL matching with prices and ratings from the database above.",
            "For cheapest/best/luxury: actually sort and give real answers with real prices.",
            "For reviews: quote real ones from the database above.",
            "For personal questions (my points, my bookings, my wishlist): use the user profile above.",
            "For company questions: answer with complete authority.",
            "NEVER say you do not know - you have full access to everything above.",
        ]
        system_prompt = "\n".join(system_parts)

        messages = []
        for h in history[-10:]:
            if h.get("role") in ("user", "assistant") and h.get("content"):
                messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        client = anthropic.Anthropic(api_key=self._get_api_key())
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=system_prompt,
            messages=messages
        )
        return response.content[0].text

    def _get_api_key(self):
        import os
        from django.conf import settings
        key = getattr(settings, "ANTHROPIC_API_KEY", None) or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise ValueError("No API key configured")
        return key

    def _smart_reply(self, msg, user, ctx):
        from apps.properties.models import Property
        u = ctx["user"]
        props_raw = list(Property.objects.filter(is_active=True).prefetch_related("reviews").select_related("host"))
        stats = ctx["stats"]
        pts = u["points"]
        name = u["name"]
        tier = u["tier"]
        discount = u["discount"]

        # Greetings
        if any(w in msg for w in ["hello", "hi", "hey", "good morning", "good evening", "howdy", "sup", "yo"]):
            disc_txt = " giving you **" + str(discount) + "% off** every booking!" if discount else "."
            return ("Hey " + name + "! I am **Voya**, your AI travel concierge on Voyaga.\n\n"
                    "You are a **" + tier + "** member with **" + str(pts) + " points**" + disc_txt + "\n\n"
                    "We have **" + str(stats["active_props"]) + " properties** bookable with crypto right now. "
                    "Ask me anything about destinations, pricing, your bookings, or how Voyaga works!")

        # Show all properties
        if any(w in msg for w in ["all properties", "show all", "list all", "everything available", "what do you have", "show me everything"]):
            if not props_raw:
                return "No properties listed yet - check back soon!"
            lines = ["**" + p.title + "** - " + p.city + ", " + p.country + " | $" + str(p.price_per_night) + "/night | " + p.property_type + " | " + (str(p.avg_rating) + " stars" if p.avg_rating else "New") for p in props_raw]
            return "All **" + str(len(props_raw)) + " active listings** on Voyaga:\n\n" + "\n".join(lines) + "\n\nType a city or budget and I will narrow it down!"

        # City/country search
        city_matches = [p for p in props_raw if p.city.lower() in msg or p.country.lower() in msg]
        if city_matches:
            lines = ["* **" + p.title + "** - $" + str(p.price_per_night) + "/night | " + p.property_type + " | " + (str(p.avg_rating) + " stars" if p.avg_rating else "New listing") for p in city_matches]
            location = city_matches[0].city + ", " + city_matches[0].country
            return ("**" + str(len(city_matches)) + " " + ("property" if len(city_matches) == 1 else "properties") + " found in " + location + ":**\n\n" +
                    "\n".join(lines) + "\n\nWant full details, amenities, or reviews for any of these? Just ask!")

        # Budget / cheapest
        if any(w in msg for w in ["cheapest", "budget", "affordable", "cheap", "lowest price", "least expensive", "low cost"]):
            if props_raw:
                sorted_p = sorted(props_raw, key=lambda p: float(p.price_per_night))[:5]
                lines = [str(i+1) + ". **" + p.title + "** - $" + str(p.price_per_night) + "/night in " + p.city + " | " + p.property_type for i, p in enumerate(sorted_p)]
                return "**Most affordable options on Voyaga:**\n\n" + "\n".join(lines) + "\n\nAll bookable with BTC, ETH, USDT, SOL and more!"

        # Luxury / expensive
        if any(w in msg for w in ["expensive", "luxury", "premium", "most expensive", "high end", "penthouse", "villa", "finest", "best properties"]):
            if props_raw:
                sorted_p = sorted(props_raw, key=lambda p: float(p.price_per_night), reverse=True)[:5]
                lines = [str(i+1) + ". **" + p.title + "** - $" + str(p.price_per_night) + "/night in " + p.city + " | " + (str(p.avg_rating) + " stars" if p.avg_rating else "New") for i, p in enumerate(sorted_p)]
                return "**Premium listings on Voyaga:**\n\n" + "\n".join(lines) + "\n\nOur finest properties. Want amenities or guest reviews for any?"

        # Best rated
        if any(w in msg for w in ["best rated", "highest rated", "top rated", "most popular", "most reviewed", "recommended", "best reviewed"]):
            rated = [p for p in props_raw if p.avg_rating]
            if rated:
                sorted_p = sorted(rated, key=lambda p: float(p.avg_rating), reverse=True)[:5]
                lines = [str(i+1) + ". **" + p.title + "** - " + str(p.avg_rating) + " stars | $" + str(p.price_per_night) + "/night | " + p.city for i, p in enumerate(sorted_p)]
                return "**Top rated properties on Voyaga:**\n\n" + "\n".join(lines) + "\n\nLoved by our guests!"
            return "No rated properties yet - all listings are new! Be the first to review after your stay."

        # Reviews
        if any(w in msg for w in ["review", "reviews", "rating", "what do guests say", "feedback", "testimonial"]):
            if ctx["review_lines"]:
                sample = ctx["review_lines"][:6]
                extra = " ...and " + str(ctx["review_count"] - 6) + " more." if ctx["review_count"] > 6 else ""
                return ("**What guests are saying (" + str(ctx["review_count"]) + " total reviews):**\n\n" +
                        "\n".join(["* " + r for r in sample]) + extra +
                        "\n\nAsk about a specific property for its reviews!")
            return "No reviews yet - be the first to review after your stay!"

        # Loyalty / points
        if any(w in msg for w in ["loyalty", "points", "tier", "rewards", "discount", "silver", "gold", "platinum", "explorer", "how many points"]):
            if pts < 500:
                progress = "You need **" + str(500 - pts) + " more points** to reach Silver (5% off every booking)"
            elif pts < 2000:
                progress = "You need **" + str(2000 - pts) + " more points** to reach Gold (7% off every booking)"
            elif pts < 5000:
                progress = "You need **" + str(5000 - pts) + " more points** to reach Platinum (10% off every booking)"
            else:
                progress = "You are at **Platinum** - the maximum tier! 10% off every booking!"
            return ("**Your Loyalty Status:**\n\n"
                    "Tier: **" + tier + "** | Points: **" + str(pts) + "** | Discount: **" + str(discount) + "% off**\n\n"
                    + progress + "\n\n"
                    "**How tiers work:**\n"
                    "* Explorer (0 pts) - Standard pricing\n"
                    "* Silver (500 pts) - 5% off all bookings\n"
                    "* Gold (2,000 pts) - 7% off all bookings\n"
                    "* Platinum (5,000 pts) - 10% off all bookings\n\n"
                    "Earn **1 point per $1 spent**. Points never expire and discounts apply automatically at checkout!")

    
        if any(w in msg for w in ["my booking", "my trip", "my stay", "my reservation", "past booking", "booking history", "where have i stayed"]):
            if u["bookings"]:
                lines = ["* " + b for b in u["bookings"]]
                return ("**Your bookings (" + str(u["booking_count"]) + " total):**\n\n" +
                        "\n".join(lines) + "\n\nManage, view details, or cancel at **/bookings**")
            return ("You have no bookings yet! Browse our **" + str(stats["active_props"]) +
                    " properties** at /properties to plan your first trip!")

        
        if any(w in msg for w in ["wishlist", "saved", "favourite", "favorite", "heart", "saved properties", "liked"]):
            if u["wishlist"]:
                return ("**Your wishlist (" + str(len(u["wishlist"])) + " saved properties):**\n\n" +
                        "\n".join(["* " + w for w in u["wishlist"]]) +
                        "\n\nView and manage at **/wishlist**. Want details on any of these?")
            return "Your wishlist is empty! Click the heart on any property to save it. Browse /properties to explore."

        # Wallet
        if any(w in msg for w in ["wallet", "balance", "money", "fund", "credit", "how much"]):
            return ("**Your Wallet:**\n\nCurrent balance: **$" + str(round(u["wallet"], 2)) + "**\n\n"
                    "Your wallet is used for refunds when you cancel a booking. "
                    "New bookings are paid directly via cryptocurrency to a generated address.")

        # Carbon / eco
        if any(w in msg for w in ["carbon", "environment", "eco", "green", "sustainable", "co2", "energy", "water", "footprint"]):
            return ("**Carbon Footprint Tracking on Voyaga:**\n\n"
                    "Every property page shows your environmental impact per night:\n"
                    "* CO2 emissions (kg) - based on property type and amenities\n"
                    "* Energy usage (kWh) - higher for pool properties (+40%)\n"
                    "* Water consumption (L) - varies by size and type\n\n"
                    "**Ratings:** Low (green) / Medium (amber) / High (red)\n\n"
                    "Cabins and studios have the lowest impact (~5-6kg CO2/night). "
                    "Penthouses and pool villas the highest (~22+ kg CO2/night). Choose consciously!")

        # How to book
        if any(w in msg for w in ["how to book", "booking process", "how does it work", "how do i book", "crypto payment", "how to pay", "payment process"]):
            return ("**How booking works on Voyaga:**\n\n"
                    "1. Browse properties and select your dates\n"
                    "2. Choose your crypto: BTC, ETH, USDT, SOL, LTC, BNB, or DOGE\n"
                    "3. A unique wallet address is generated for your exact payment\n"
                    "4. Send the crypto amount to the address\n"
                    "5. Blockchain verification happens automatically\n"
                    "6. **Booking confirmed instantly!** You get a notification.\n\n"
                    "The host receives **97% of the payment immediately** - not after checkout.\n"
                    "Cancel anytime for a **100% instant refund** to your wallet. No forms, no waiting.")

        # Hosting
        if any(w in msg for w in ["host", "list my property", "list a property", "become a host", "earn money", "add listing", "add property"]):
            return ("**Become a Host on Voyaga:**\n\n"
                    "* **Anyone** can list a property - no approval, no waiting\n"
                    "* Go to **/list-property** to get started\n"
                    "* Upload up to **10 photos** with drag and drop\n"
                    "* Set your own price, amenities, max guests, and rules\n"
                    "* Listing goes **live instantly**\n\n"
                    "**What you earn:**\n"
                    "* **97% of every booking** - paid to your wallet the moment a guest confirms\n"
                    "* Real-time notifications on every new booking and cancellation\n"
                    "* Full analytics dashboard at **/analytics**\n"
                    "* Delist or relist anytime from **/my-listings**\n\n"
                    "Zero listing fees. Zero approval. Just 3% per booking.")

        # About Voyaga
        if any(w in msg for w in ["about voyaga", "what is voyaga", "company", "who made", "who built", "team", "voyaga de", "about the platform"]):
            return ("**About Voyaga:**\n\n"
                    "Voyaga is a **next-generation luxury travel platform** built by **Team Voyaga(DE)**. "
                    "We let travellers book extraordinary properties worldwide using cryptocurrency - "
                    "no banks, no cards, no hidden fees.\n\n"
                    "**Live Platform Stats:**\n"
                    "* " + str(stats["users"]) + " registered users\n"
                    "* " + str(stats["hosts"]) + " active hosts\n"
                    "* " + str(stats["active_props"]) + " live property listings\n"
                    "* " + str(stats["bookings"]) + " confirmed bookings\n"
                    "* " + str(ctx["review_count"]) + " verified guest reviews\n\n"
                    "**Key features:** Crypto payments, instant host payouts, AI concierge, "
                    "live availability calendars, loyalty rewards, carbon tracking, wishlist, host analytics\n\n"
                    "Support: **help@voyaga.com** | Full info: **/about**")

        # Cancellation
        if any(w in msg for w in ["cancel", "refund", "cancellation", "get money back", "cancel booking"]):
            return ("**Cancellation Policy on Voyaga:**\n\n"
                    "* Cancel **any confirmed booking** at any time - no questions asked\n"
                    "* **100% full refund** back in your wallet instantly\n"
                    "* Host payout is **automatically reversed** - no manual action needed\n"
                    "* No waiting period, no processing time, no forms\n"
                    "* The refund appears in your Voyaga wallet within seconds\n\n"
                    "To cancel: go to **/bookings** and click Cancel on your booking. Done.")

        # Security
        if any(w in msg for w in ["security", "safe", "secure", "privacy", "data protection", "trust", "is it safe"]):
            return ("**Security on Voyaga:**\n\n"
                    "* **JWT authentication** - short-lived tokens with auto-refresh\n"
                    "* **OTP email verification** - confirm your account on signup\n"
                    "* **PBKDF2 password hashing** - passwords never stored in plaintext\n"
                    "* **On-chain payment verification** - every crypto transaction verified on blockchain\n"
                    "* **Role-based access control** - guests, hosts, and admins fully separated\n"
                    "* **Full audit logging** - every booking and payment action timestamped\n\n"
                    "Your data is never sold. We are built on transparency and trust.")

        # Stats
        if any(w in msg for w in ["how many", "statistics", "stats", "numbers", "total users", "total properties"]):
            return ("**Voyaga Live Platform Stats:**\n\n"
                    "Registered users: **" + str(stats["users"]) + "**\n"
                    "Active hosts: **" + str(stats["hosts"]) + "**\n"
                    "Live property listings: **" + str(stats["active_props"]) + "**\n"
                    "Confirmed bookings: **" + str(stats["bookings"]) + "**\n"
                    "Verified reviews: **" + str(ctx["review_count"]) + "**\n\n"
                    "Growing every day!")

        # Contact / support
        if any(w in msg for w in ["contact", "support", "help email", "email us", "get help", "problem", "issue", "complaint"]):
            return ("**Get Help from Voyaga:**\n\n"
                    "Email: **help@voyaga.com** - we respond within 24 hours\n\n"
                    "I can also answer most questions right here! Ask me about:\n"
                    "* Any property on the platform\n"
                    "* Your bookings, points, or wishlist\n"
                    "* How payments work\n"
                    "* Cancellations and refunds\n"
                    "* Hosting and earning on Voyaga")

        # What can you do
        if any(w in msg for w in ["what can you", "help me", "what do you know", "capabilities", "what can voya", "can you help"]):
            return ("**Everything I can help you with:**\n\n"
                    "* Find properties by city, budget, type, or rating\n"
                    "* Show cheapest, best-rated, or most luxurious options\n"
                    "* Read real guest reviews for any property\n"
                    "* Explain crypto booking process step by step\n"
                    "* Check your loyalty points, tier, and progress\n"
                    "* Show your full booking history\n"
                    "* View your wishlist\n"
                    "* Check your wallet balance\n"
                    "* Explain hosting and earning on Voyaga\n"
                    "* Answer any question about the company\n"
                    "* Explain carbon footprint tracking\n"
                    "* Help with cancellations and refunds\n\n"
                    "Just ask naturally - I understand everything!")

        # Default smart fallback with real data
        prop_preview = ["* **" + p.title + "** - " + p.city + " | $" + str(p.price_per_night) + "/night" for p in props_raw[:4]]
        return ("I am Voya, your AI concierge! We have **" + str(stats["active_props"]) + " properties** available right now:\n\n" +
                "\n".join(prop_preview) + ("\n* ...and " + str(len(props_raw) - 4) + " more!" if len(props_raw) > 4 else "") +
                "\n\nTry asking:\n* 'Show properties in Mumbai'\n* 'What is the cheapest stay?'\n"
                "* 'Best rated properties'\n* 'How do I book with Bitcoin?'\n* 'What are my loyalty points?'")


class NotificationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        notifs = Notification.objects.filter(user=request.user)[:30]
        data = [{"id": n.id, "title": n.title, "message": n.message, "type": n.notif_type,
                 "link": n.link, "is_read": n.is_read, "created_at": n.created_at.isoformat()} for n in notifs]
        unread = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({"results": data, "unread": unread})

    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({"message": "All marked as read"})


class NotificationReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        Notification.objects.filter(id=pk, user=request.user).update(is_read=True)
        return Response({"message": "Marked as read"})