# −*− coding: UTF−8 −*−
from django.db import models
import datetime
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext, ugettext_lazy as _
from mergedobject import MergedObject
from vobject import iCalendar
from eventtools.smartdatetimerange import SmartDateTimeRange
from eventtools.deprecated import deprecated


"""
Occurrences represent an occurrence of an event, which have been lazily generated by one of the event's OccurrenceGenerators.

Occurrences are NOT usually saved to the database, since there is potentially an infinite number of them (for events that repeat with no end date).

However, if a particular occurrence is exceptional in any way (by changing the timing parameters, or by cancelling the occurrence, or by linking to an EventVariation), then it should be saved to the database as an exception.

When generating a set of occurrences, the generator checks to see if any exceptions have been saved to the database.
"""

class OccurrenceBase(models.Model):
    
    # injected by EventModelBase:
    # generator = models.ForeignKey(somekindofOccurrenceGenerator)
    # _varied_event = models.ForeignKey(somekindofEventVariation)
    
    #These four work as a key to the Occurrence
    unvaried_start_date = models.DateField(_("unvaried start date"), db_index=True)
    unvaried_start_time = models.TimeField(_("unvaried start time"), db_index=True, null=True)
    unvaried_end_date = models.DateField(_("unvaried end date"), db_index=True, null=True, help_text=_("if omitted, start date is assumed"))
    unvaried_end_time = models.TimeField(_("unvaried end time"), db_index=True, null=True)
    
    # These are usually the same as the unvaried, but may not always be.
    varied_start_date = models.DateField(_("varied start date"), blank=True, null=True, db_index=True)
    varied_start_time = models.TimeField(_("varied start time"), blank=True, null=True, db_index=True)
    varied_end_date = models.DateField(_("varied end date"), blank=True, null=True, db_index=True, help_text=_("if omitted, start date is assumed"))
    varied_end_time = models.TimeField(_("varied end time"), blank=True, null=True, db_index=True, help_text=_("if omitted, start time is assumed"))
    
    cancelled = models.BooleanField(_("cancelled"), default=False)
    hide_from_lists = models.BooleanField(_("hide from lists"), default=False, help_text="Hide this occurrence instead of explicitly cancelling it.")
    full = models.BooleanField(_("fully booked"), default=False)

    class Meta:
        verbose_name = _("occurrence")
        verbose_name_plural = _("occurrences")
        abstract = True
        unique_together = ('generator', 'unvaried_start_date', 'unvaried_start_time', 'unvaried_end_date', 'unvaried_end_time')


    def __init__(self, *args, **kwargs):

        uvtr = kwargs.get('unvaried_timerange', None)
        if uvtr:
            kwargs['unvaried_start_date'] = uvtr.sd
            kwargs['unvaried_start_time'] = uvtr.st
            kwargs['unvaried_end_date'] = uvtr.ed
            kwargs['unvaried_end_time'] = uvtr.et
            del kwargs['unvaried_timerange']
 
        vtr = kwargs.get('varied_timerange', None)
        if vtr:
            kwargs['varied_start_date'] = vtr.sd
            kwargs['varied_start_time'] = vtr.st
            kwargs['varied_end_date'] = vtr.ed
            kwargs['varied_end_time'] = vtr.et
            del kwargs['varied_timerange']           
        
        # by default, create items with varied values the same as unvaried
        for uv_key, v_key in [
            ('unvaried_start_date', 'varied_start_date'),
            ('unvaried_start_time', 'varied_start_time'),
            ('unvaried_end_date', 'varied_end_date'),
            ('unvaried_end_time', 'varied_end_time'),
        ]:
            if not kwargs.has_key(v_key):
                if kwargs.has_key(uv_key):
                    kwargs[v_key] = kwargs[uv_key]
                else:
                    kwargs[v_key] = None
        
        super(OccurrenceBase, self).__init__(*args, **kwargs)    
    
    def clean(self):
        """ check that the end datetime must be after start date, and that end time is not supplied without a start time. """
        try:
            self.timerange
            self.unvaried_timerange
        except AttributeError as e:
            raise ValidationError(e)

    @property
    def timerange(self):
        return SmartDateTimeRange(self.varied_start_date, self.varied_start_time, self.varied_end_date, self.varied_end_time)
    varied_timerange = timerange

    @property
    def unvaried_timerange(self):
        return SmartDateTimeRange(self.unvaried_start_date, self.unvaried_start_time, self.unvaried_end_date, self.unvaried_end_time)
        
    def _get_varied_event(self):
        try:
            return getattr(self, "_varied_event", None)
        except:
            return None
    def _set_varied_event(self, v):
        if "_varied_event" in dir(self): #for a very weird reason, hasattr(self, "_varied_event") fails. Perhaps this is because it is injected by __init__ in the metaclass, not __new__.
            self._varied_event = v
        else:
            raise AttributeError("You can't set an event variation for an event class with no 'varied_by' attribute.")
    varied_event = property(_get_varied_event, _set_varied_event)

    def _get_unvaried_event(self):
        return self.generator.event
    unvaried_event = property(_get_unvaried_event)
               
    def _merged_event(self): #bit slow, but friendly
        return MergedObject(self.unvaried_event, self.varied_event)
    event = merged_event = property(_merged_event)
    
    def _is_moved(self):
        return self.unvaried_timerange != self.varied_timerange
    is_moved = property(_is_moved)
    
    def _is_varied(self):
        if self.varied_event:
            return True
        return self.is_moved or self.cancelled or self.hide_from_lists or self.full
    is_varied = property(_is_varied)
       
    def cancel(self):
        self.cancelled = True
        self.save()

    def uncancel(self):
        self.cancelled = False
        self.save()

    def __unicode__(self):
        return ugettext("%(event)s: %(day)s") % {
            'event': self.event.title,
            'day': unicode(self.timerange),
        }

    def __cmp__(self, other): #used for sorting occurrences.
        return cmp(self.timerange, other.timerange)

    def __eq__(self, other):
        if isinstance(other, OccurrenceBase):
            return self.event == other.event and \
                self.timerange == other.timerange and \
                self.unvaried_timerange == other.unvaried_timerange
        return super(OccurrenceBase, self).__eq__(other)

    @property
    def reason_for_variation(self):
        """
        What to put as reasons in a list of variations. Assume date is printed elsewhere.
        """
        
        if not self.is_varied:
            return None
        
        # varied event reason trumps all
        if self.varied_event:
            return self.varied_event.reason
        
        # cancellation trumps date/time changes
        if self.cancelled:
            return "Cancelled"

        if self.full:
            return "Fully Booked"
            
        if self.hide_from_lists:
            return "Not available"

        messages = []
        
        if self.timerange.start_date != self.unvaried_timerange.start_date:
            messages.append("new date")

        dd = None
        if self.timerange.start_time < self.unvaried_timerange.start_time:
            dd = "starts earlier at %s"
        elif self.timerange.start_time > self.unvaried_timerange.start_time:
            dd = "starts later at %s"

        if dd:
            messages.append(dd % self.timerange.robot_time_description())
        else:        
            if self.timerange.end_time < self.unvaried_timerange.end_time:
                dd = "ends earlier at %s"
            elif self.timerange.end_time > self.unvaried_timerange.end_time:
                dd = "ends later at %s"
                
                if dd:
                    messages.append(dd % self.timerange.robot_end_time_description())
        
        return "; ".join(messages)
        
    @property
    def generated_id(self):
        """
        this occurrence is unique for an EVENT (the un/varied event) and for a particular DAY (start) and a particular place in a list
        """
        start_date = self.timerange.start_date
        occurrence_list = self.generator.event.get_occurrences(start_date, start_date + datetime.timedelta(1))
        return occurrence_list.index(self)

    def check_for_exceptions(self):
        """
        Pass out an exceptional occurrence, if one exists in the db, or self if no exceptional occurrence exists in the db.
        """
        try:
            return type(self).objects.get(
                generator = self.generator,
                unvaried_start_date = self.unvaried_start_date,
                unvaried_start_time = self.unvaried_start_time,
                unvaried_end_date = self.unvaried_end_date,
                unvaried_end_time = self.unvaried_end_time,
            )
        except type(self).DoesNotExist:
            return self


    @property
    def as_icalendar(self):
        """
        Returns the occurrence as an iCalendar object
        """
        ical = iCalendar()
        cal.add('method').value = 'PUBLISH'  # IE/Outlook needs this
        ical.add('vevent').add('summary').value = self.merged_event.title
        if self.timerange.dates_only:            
            ical.vevent.add('dtstart').value = self.timerange.start_date
            ical.vevent.add('dtend').value = self.timerange.end_date
        else:
            ical.vevent.add('dtstart').value = self.timerange.start_datetime
            ical.vevent.add('dtend').value = self.timerange.end_datetime
        if self.cancelled:
            ical.vevent.add('method').value = 'CANCEL'
            ical.vevent.add('status').value = 'CANCELLED'
        return ical 
        
    """
    From:
    http://blog.thescoop.org/archives/2007/07/31/django-ical-and-vobject/

        cal = vobject.iCalendar()
        cal.add('method').value = 'PUBLISH'  # IE/Outlook needs this
        for event in event_list:
            vevent = cal.add('vevent')
            ... # add your event details
        icalstream = cal.serialize()
        response = HttpResponse(icalstream, mimetype='text/calendar')
        response['Filename'] = 'filename.ics'  # IE needs this
        response['Content-Disposition'] = 'attachment; filename=filename.ics'
    """
    
    #deprecations    
    @property
    @deprecated
    def reason(self):
        return self.reason_for_variation()

    @property
    @deprecated
    def varied_range_string(self):
        return self.timerange.robot_description()

    @property
    @deprecated
    def date_description(self):
        return self.timerange.start_description()

    @property
    @deprecated
    def unvaried_range_string(self):
        return self.unvaried_timerange.robot_description()

    @property
    @deprecated
    def start(self):
         return self.timerange.start

    @property
    @deprecated
    def end(self):
        return self.timerange.end

    @property
    @deprecated
    def original_start(self):
         return self.unvaried_timerange.start

    @property
    @deprecated
    def original_end(self):
        return self.unvaried_timerange.end

    @property
    @deprecated
    def start_time(self):
        return self.timerange.start_time
         
    @property
    @deprecated
    def end_time(self):
        return self.timerange.end_time

    @property
    @deprecated
    def start_date(self):
        return self.timerange.start_date
         
    @property
    @deprecated
    def end_date(self):
        return self.timerange.end_date
         
    @property
    @deprecated
    def duration(self):
        return self.timerange.duration()
         
    @property
    @deprecated
    def humanized_duration(self):
        return self.timerange.humanized_duration()