# utils/email_utils.py

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags


def send_payment_receipt(payment):
    """Send payment receipt email to tenant"""
    try:
        subject = f'Payment Receipt - {payment.payment_for_month.strftime("%B %Y")}'
        
        context = {
            'payment': payment,
            'tenant': payment.tenant,
            'tenancy': payment.tenancy,
            'room': payment.tenancy.room,
            'apartment': payment.apartment,
            'site_url': settings.SITE_URL,
        }
        
        # Render HTML email
        html_content = render_to_string('emails/payment_receipt.html', context)
        text_content = strip_tags(html_content)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[payment.tenant.email] if payment.tenant.email else []
        )
        email.attach_alternative(html_content, "text/html")
        
        if payment.tenant.email:
            email.send()
            return True
        return False
    except Exception as e:
        print(f"Error sending receipt email: {str(e)}")
        return False