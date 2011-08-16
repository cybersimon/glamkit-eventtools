# −*− coding: UTF−8 −*−
from django.db import models, transaction
from django.db.models.base import ModelBase
from django.utils.translation import ugettext, ugettext_lazy as _
from django.core import exceptions

from dateutil import rrule

from eventtools.utils import datetimeify
from eventtools.conf import settings
from eventtools.utils.pprint_timespan import (
    pprint_datetime_span, pprint_date_span)

from datetime import date, time, datetime, timedelta

class GeneratorModel(models.Model):
    """
    Generates occurrences.
    """

    #define a FK called 'event' in the subclass
    event_start = models.DateTimeField(db_index=True)
    event_end = models.DateTimeField(blank=True, db_index=True)
    rule = models.ForeignKey("eventtools.Rule")
    repeat_until = models.DateTimeField(null = True, blank = True, help_text=_(u"These start dates are ignored for one-off events."))

    class Meta:
        abstract = True
        ordering = ('event_start',)
        verbose_name = "repeating occurrence"
        verbose_name_plural = "repeating occurrences"

    def __unicode__(self):
        return u"%s, %s" % (self.event, self.robot_description())
    
    def clean(self, ExceptionClass=exceptions.ValidationError):
        if self.event_end is None:
            self.event_end = self.event_start
    
        self.event_start = datetimeify(self.event_start, clamp="min")
        self.event_end = datetimeify(self.event_end, clamp="max")
        if self.repeat_until is not None:
            self.repeat_until = datetimeify(self.repeat_until, clamp="max")

        if self.event_end.time == time.min:
            self.event_end.time == time.max

        if not self.rule_id:
            raise ExceptionClass('a rule must be supplied')
    
        if self.event_start > self.event_end:
            raise ExceptionClass('start must be earlier than end')
        if self.repeat_until is not None and \
                self.repeat_until < self.event_end:
            raise ExceptionClass(
                'repeat_until must not be earlier than start')
        # This data entry mistake is common enough to justify a slight hack.
        if self.rule.frequency == 'DAILY' \
                and self.event_duration() > timedelta(1):
            raise ExceptionClass(
                'Daily events cannot span multiple days; the event start and \
                end dates should be the same.'
            )
            
        self.is_clean = True
        super(GeneratorModel, self).clean()
    
    
    @transaction.commit_on_success()
    def save(self, *args, **kwargs):
        """
        Generally (and for a combination of field changes), we take a
        two-pass approach:
    
         1) First update existing occurrences to match update-compatible fields.
         2) Then synchronise the candidate occurrences with the existing
            occurrences.
            * For candidate occurrences that exist, do nothing.
            * For candidate occurrences that do not exist, add them.
            * For existing occurrences that are not candidates, unhook them from
                the generator.

        Finally, we also update other generators, because they might have had
        clashing occurrences which no longer clash.
        """
        
        cascade = kwargs.pop('cascade', True)
        
        if not getattr(self, 'is_clean', False):
            # if we're saving directly, the ModelForm clean isn't called, so
            # we do it here.
            self.clean(ExceptionClass=AttributeError)
        
        # Occurrences updates/generates
        if self.pk:
            self._update_existing_occurrences() # need to do this before save, so we can detect changes

        r = super(GeneratorModel, self).save(*args, **kwargs)
        self._sync_occurrences() #need to do this after save, so we have a pk to hang new occurrences from.
    
        # finally, we should also update other generators, because they might 
        # have had clashing occurrences
        if cascade:
            for generator in self.event.generators.exclude(pk=self.pk):
                generator.save(cascade=False)
        
        return r
        
    def event_duration(self):
        return self.event_end-self.event_start
    
    @classmethod
    def EventModel(cls):
        return cls._meta.get_field('event').rel.to
        
    def _generate_dates(self):
        if self.rule is None:
            yield self.event_start
            raise StopIteration
        
        rule = self.rule.get_rrule(dtstart=self.event_start)
        date_iter = iter(rule)
        drop_dead_date = self.repeat_until or datetime.now() + settings.DEFAULT_GENERATOR_LIMIT
                
        while True:
            d = date_iter.next()
            if d > drop_dead_date:
                break
            yield d
    
    @transaction.commit_on_success()
    def _update_existing_occurrences(self):
        """
        When you change a generator and save it, it updates existing occurrences
        according to the following rules:
        
        Generally, we never automatically delete occurrences, we unhook them
        from the generator, and make them manual. This is to prevent losing
        information like tickets sold or shout-outs. We leave implementors to
        decide the workflow in these cases. We want to minimise the number of
        events that are unhooked, however. So:
    
         * If start time or end date or time is changed, then no occurrences are
           added or removed - we timeshift all occurrences. We assume that
           visitors/ticket holders are alerted to the time change elsewhere.
    
         * If other fields are changed - repetition rule, repeat_until, start
           date - then there is a chance that Occurrences will be added or
           removed.
    
         * Occurrences that are added are fine, they are added in the normal
           way.
           
         * Occurrences that are removed are unhooked, for reasons
           described above.
        """
        
        """
        Pass 1)
        if start date or time is changed:
            update the start times of my occurrences
        if end date or time is changed:
            update the end times of my occurrences
                        
        """
        
        # TODO: it would be ideal to minimise the consequences of shifting one
        # occurrence into another - ie to leave most occurrences untouched and 
        # to create only new ones and unhook ungenerated ones.
        # I tried this by using start date (which is unique per generator) as
        # a nominal 'key', but it gets fiddly when you want to vary the end
        # date to before the old start date. For now we'll just update the dates
        # and times.

        saved_self = type(self).objects.get(pk=self.pk)
        
        start_shift = self.event_start - saved_self.event_start
        end_shift = self.event_end - saved_self.event_end
        duration = self.event_duration()
        
        if start_shift or end_shift:
            for o in self.occurrences.all():
                o.start += start_shift
                o.end = o.start + duration
                o.save()

    
    @transaction.commit_on_success()
    def _sync_occurrences(self):
    
        """
            * For candidate occurrences that exist, do nothing.
            * For candidate occurrences that do not exist, add them.
            * For existing occurrences that are not candidates, unhook them from the generator
            
        In detail:
        Get a list, A, of already-generated occurrences.
        
        Generate candidate Occurrences.
        For each candidate Occurrence:
            if it exists for the event:
                if I created it, unhook, and remove from the list A.
                else do nothing
            if it is an exclusion, do nothing
            otherwise create it.
            
        The items remaining in list A are 'orphan' occurrences, that were
        previously generated, but would no longer be. These are unhooked from
        the generator.
        """
        
        all_occurrences = self.event.occurrences.all() #regardless of generator
        unaccounted_for = set(self.occurrences.all())
        
        event_duration = self.event_duration()
        
        for start in self._generate_dates():
            # if the proposed occurrence exists, then don't make a new one.
            # However, if it belongs to me: 
            #       and if it is marked as an exclusion:
            #           do nothing (it will later get unhooked)
            #       else:
            #           remove it from the set of unaccounted_for
            #           occurrences so it stays hooked up
            
            try:
                o = all_occurrences.filter(start=start)[0]
                if o.generated_by == self:
                    if not o.is_exclusion():
                        unaccounted_for.discard(o)
                continue
            except IndexError:
                # no occurrence exists yet.
                pass

            # if the proposed occurrence is an exclusion, don't save it.
            if self.event.exclusions.filter(
                event=self.event, start=start
            ).count():
                continue            

            #OK, we're good to go.
            end = start + event_duration
            o = self.occurrences.create(event=self.event, start=start, end=end) #implied generated_by = self
    
        # Finally, unhook any unaccounted_for occurrences
        for o in unaccounted_for:
            o.generated_by = None
            o.save()
    
    # This is scrappy
    def robot_description(self):
        return u'\n'.join(
            [pprint_datetime_span(start, end) + repeat_description \
            for start, end, repeat_description in self.get_spans()])
    
    # This is scrappy too
    def get_spans(self):
        if self.rule:
            if self.occurrences.count() > 3:
                if self.repeat_until:
                    repeat_description = u', repeating %s until %s' % (
                        self.rule,
                        pprint_date_span(self.repeat_until, self.repeat_until)
                    )
                else:
                    repeat_description = u', repeating %s' % self.rule
                return [(self.event_start, self.event_end, repeat_description),]
            else:
                return [(occ.start, occ.end, u'') for occ in self.occurrences.all()]
        else:
            return [(self.event_start, self.event_end, u''),]