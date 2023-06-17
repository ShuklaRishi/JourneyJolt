from django.db import models
from authentication.models import Department, BaseModel, Users
# Create your models here.
class Poll(BaseModel):
    """stores poll details"""
    title = models.CharField(max_length= 300)
    department = models.ManyToManyField(Department, related_name = "polls")
    expiry = models.DateTimeField()

    def __str__(self):
        return self.title
    
    db_table = 'polls'


class Choice(BaseModel):
    """stores choices for each poll"""
    poll = models.ForeignKey(Poll, on_delete= models.CASCADE, related_name= "choices")
    choice_text = models.CharField(max_length= 200)
    votes = models.IntegerField(default= 0)

    def __str__(self):
        return self.choice_text
    
    db_table = 'choices'


class Vote(BaseModel):
    """stores users with their respective selected choice for poll to manage votes"""
    choice = models.ForeignKey(Choice, on_delete= models.CASCADE, related_name= 'vote')
    user = models.ForeignKey(Users, on_delete= models.CASCADE)

    class Meta:
        unique_together = (('user', 'choice'),)