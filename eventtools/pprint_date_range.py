"""
Returns nicely-presented versions of the ranges between two dates

e.g.

27-29 May 2009
27 May-1 June 2009

8 pm-12 midnight
8 am-12 noon
8.30-9 am

"""
from datetime import date, time, datetime

DAYS_IN_MONTHS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

def days_in_month(date): #January = 1
    if date.month ==2 and (date.year % 4) == 0:
        return 29
    else:
        return DAYS_IN_MONTHS[date.month-1]

def _clean_dates(date1, date2):
    if not date1:
        raise TypeError("You must provide a start date")
        
    if not date2:
        date2 = date1

    #Case: d2 is less than d1. Swap them
    if date2 < date1:
        dt = date2
        date2 = date1
        date1 = dt
        
    return date1, date2


def pprint_date_range(date1, date2, space=" ", range_str="-"):
    
    date1, date2 = _clean_dates(date1, date2)
    
    d1d = date1.day #decimal (remove leading 0s)
    d1m = date1.strftime("%B") #Month name
    d1y = date1.strftime("%Y")

    #Case: the two are equal; no range
    if date1 == date2:
        return "%d%s%s%s%s" % (d1d, space, d1m, space, d1y)        

    d2d = date2.day #decimal (remove leading 0s)
    d2m = date2.strftime("%B") #Month name
    d2y = date2.strftime("%Y")
    
    
    #get rid of redundancies
    if d1y == d2y:
        d1y = ""
        if d1m == d2m: d1m = ""
    #by now we know that d1d and d2d are different (or in different months)
    
    #Add spacing where necessary
    if d1m!="":
        if d1y!="":
            d1m = "%s%s%s" % (space, d1m, space)
        else:
            d1m = "%s%s" % (space, d1m)
            

    d2m = "%s%s%s" % (space, d2m, space)
    
    return "%s%s%s%s%s%s%s" % (d1d, d1m, d1y, range_str, d2d, d2m, d2y)
       
def humanized_date_range(date1, date2, imply_year=True, space=" ", range_str="-"):
    """
    Like the above, except that if date1 and date2 exactly define a month, then just name the month, rather than the date ranges.
    Ditto with an exactly-defined year -- just return the year.
    
    Also, if imply_year=True, then if both dates fall with in this year, then omit the year (unless the dates exactly describe the year).
    """
    
    date1, date2 = _clean_dates(date1, date2)

    
    if date1.day == 1 and date2.day == days_in_month(date2): #we've got an entire month range.
        if date1.year == date2.year:
            if date1.month == date2.month:
                ds = "%s%s%s" % (date2.strftime("%B"), space, date2.year)
            else:
                if date1.month ==1 and date2.month == 12:
                    ds = "%s" % date1.year
                else:
                    ds = "%s%s%s%s%s" % (date1.strftime("%B"), range_str, date2.strftime("%B"), space, date2.year)
        else:
            if date1.month ==1 and date2.month == 12:
                ds = "%s%s%s" % (date1.year, range_str, date2.year)
            else:    
                ds = "%s%s%s%s%s%s%s" % (date1.strftime("%B"), space, date1.year, range_str, date2.strftime("%B"), space, date2.year)
    else:
        ds = pprint_date_range(date1, date2, space, range_str)
        
    if imply_year:
        today = date.today()
        if date1.year == date2.year and date1.year == today.year and ds != "%s" % date1.year:
            #strip off the year
            return ds[:-5]
    return ds
    
    
def pprint_time_range(time1, time2, separator=":", am="am", pm="pm", midnight="midnight", noon="noon", range_str="-"):
    
        apdict = {
            'am': am,
            'pm': pm,
            'midnight': midnight,
            'noon': noon,
            '': '',
        }
    
        ##THIS IS NOT LOCALE-TOLERANT. Assumption of am/pm.
        if time1 is not None:
                
            t1h = str(int(time1.strftime("%I"))) #decimal (remove leading 0s)
            t1m = time1.strftime("%M") #leading 0s       
            t1ap = time1.strftime("%p").lower()

            if t1h == "12" and t1m == "00":
                if t1ap == "am":
                    t1ap = "midnight"
                else:
                    t1ap = "noon"
                t1h = ""
        
            #Case: the two are equal; no range
            if (time1 == time2):
                return "%s%s%s%s" % (t1h, separator, t1m, apdict[t1ap])
            
            if time2 is None:
                return "from %s%s%s%s" % (t1h, separator, t1m, apdict[t1ap])

        t2h = str(int(time2.strftime("%I"))) #decimal (remove leading 0s)
        t2m = time2.strftime("%M") #leading 0s       
        t2ap = time2.strftime("%p").lower()
        if t2h == "12" and t2m == "00":
            if t2ap == "am":
                t2ap = "midnight"
            else:
                t2ap = "noon"
            t2h = ""
        
        if t2m != "00":
            t2 = t2h+separator+t2m
        else:
            t2 = t2h
    
        if time1 is not None:
            #get rid of redundancies
            #render the minutes only if necessary
            if t1m != "00":
                t1 = t1h+separator+t1m
            else:
                t1 = t1h
            # and am/pm
            if t1ap == t2ap and time1 < time2:
                t1ap = ""
             
            return "%s%s%s%s%s" % (t1, apdict[t1ap], range_str, t2, apdict[t2ap])
        else:
            return "until %s%s" % (t2, apdict[t2ap])
            
def pprint_datetime_range(dt1, dt2, infer_all_day=False):
    date1 = dt1.date()
    time1 = dt1.time()
    date2 = dt2.date()
    time2 = dt2.time()
    
    if time1 == time.min and time2 == time.max:
        if infer_all_day:
            return "%s, all day", pprint_date_range(date1, date2)
        return pprint_date_range(date1, date2)
    else:
        return "%s, %s" % (pprint_date_range(date1, date2), pprint_time_range(time1, time2))
              
if __name__ == "__main__":

    import unittest
    
    class TestDateTimeRange(unittest.TestCase):
        def setUp(self):
            self.ae = self.assertEqual

        def test_normality(self):
            dt1 = datetime(2010, 9, 23, 10, 42)
            dt2 = datetime(2010, 9, 23, 16, 42)
            self.ae(pprint_datetime_range(dt1, dt2), "23 September 2010, 10:42am-4:42pm")

        def test_minmax(self):
            dt1 = datetime.combine(date(2010, 9, 23), time.min)
            dt2 = datetime.combine(date(2010, 9, 24), time.max)
            self.ae(pprint_datetime_range(dt1, dt2), "23-24 September 2010")


    class TestTimeRange(unittest.TestCase):
        def setUp(self):
            self.ae = self.assertEqual
        
        def test_normality(self):
            time1 = time(10,20)
            time2 = time(10,40)
            self.ae(pprint_time_range(time1, time2), "10:20-10:40am")
            self.ae(pprint_time_range(time1, time1), "10:20am")
            self.ae(pprint_time_range(time1, None), "from 10:20am")
            self.ae(pprint_time_range(None, time2), "until 10:40am")
            # might just want to display this.
            self.ae(pprint_time_range(time2, time1), "10:40am-10:20am")

        def test_formatting(self):
            time1 = time(10,20)
            time2 = time(14,40)
            self.ae(pprint_time_range(time1, time2, separator=".", range_str=" to ", am=" a.m.", pm=" p.m."), "10.20 a.m. to 2.40 p.m.")
            time1 = time(00,00)
            time2 = time(12,00)
            self.ae(pprint_time_range(time1, time2,  range_str=" a ", midnight="midnuit", noon="midi"), "midnuit a midi")

        def test_overflow(self):
            time1 = time(10,50)
            time2 = time(14,40)
            self.ae(pprint_time_range(time1, time2), "10:50am-2:40pm")

        def test_simplify(self):
            time1 = time(10,00)
            time2 = time(11,00)
            time3 = time(11,30)
            midnight = time(00,00)
            noon = time(12,00)
            self.ae(pprint_time_range(time1, time2), "10-11am")
            self.ae(pprint_time_range(time1, noon), "10am-noon")
            self.ae(pprint_time_range(midnight, time2), "midnight-11am")
            self.ae(pprint_time_range(time1, time3), "10-11:30am")
           


    class TestDateRange(unittest.TestCase):
    
        def setUp(self):
            self.ae = self.assertEqual
        
        def test_normality(self):
            date1 = date(2001, 10, 10)
            date2 = date(2001, 10, 12)
            self.ae(pprint_date_range(date1, date2), "10-12 October 2001")

            date1 = date(2001, 10, 10)
            date2 = date(2001, 10, 10)
            self.ae(pprint_date_range(date1, date2), "10 October 2001")

        def test_formatting(self):
            date1 = date(2001, 10, 10)
            date2 = date(2002, 10, 12)
            self.ae(pprint_date_range(date1, date2, range_str=" to ", space="."), "10.October.2001 to 12.October.2002")
            
        def test_invalid(self):
            date1 = date(2001, 10, 10)
            date2 = date(2001, 11, 12)
            self.ae(pprint_date_range(date1, None), "10 October 2001")
            self.assertRaises(TypeError, pprint_date_range, None, date2)
            #what if the dates are not in order
            self.ae(pprint_date_range(date2, date1), "10 October-12 November 2001")
            
            # same with humanize
            self.ae(humanized_date_range(date1, None), "10 October 2001")
            self.assertRaises(TypeError, humanized_date_range, None, date2)
            #what if the dates are not in order
            self.ae(humanized_date_range(date2, date1), "10 October-12 November 2001")
                        
        def test_overflow(self):
            date1 = date(2001, 10, 10)
            date2 = date(2001, 11, 12)
            self.ae(pprint_date_range(date1, date2), "10 October-12 November 2001")

            date1 = date(2001, 10, 10)
            date2 = date(2002, 10, 12)
            self.ae(pprint_date_range(date1, date2), "10 October 2001-12 October 2002")
            
        def test_humanize_date(self):
            # Check days are omitted if the range exactly covers the month.
            date1 = date(2001, 7, 1)
            date2 = date(2001, 7, 31)
            self.ae(humanized_date_range(date1, date2), "July 2001")
            #Or if it exactly covers 2 or more months
            date1 = date(2002, 7, 1)
            date2 = date(2002, 8, 31)
            self.ae(humanized_date_range(date1, date2), "July-August 2002")
            date1 = date(2001, 7, 1)
            date2 = date(2002, 8, 31)
            self.ae(humanized_date_range(date1, date2), "July 2001-August 2002")
            date1 = date(2001, 7, 1)
            date2 = date(2002, 7, 31)
            self.ae(humanized_date_range(date1, date2), "July 2001-July 2002")
            
            
            #check that months and days are omitted if the range exactly covers the year
            date1 = date(2001, 1, 1)
            date2 = date(2001, 12, 31)
            self.ae(humanized_date_range(date1, date2), "2001")              
            date1 = date(2001, 1, 1)
            date2 = date(2003, 12, 31)
            self.ae(humanized_date_range(date1, date2), "2001-2003")              

            #Check that the year is omitted for ranges entirely in this year, unless imply_year = False
            today = date.today()
            date1 = date(today.year, 1, 12)
            date2 = date(today.year, 1, 14)
            self.ae(humanized_date_range(date1, date2), "12-14 January")
            self.ae(humanized_date_range(date1, date2, imply_year=False), "12-14 January %s" % today.year)
            date1 = date(today.year, 1, 12)
            date2 = date(today.year, 2, 14)
            self.ae(humanized_date_range(date1, date2), "12 January-14 February")
            self.ae(humanized_date_range(date1, date2, imply_year=False), "12 January-14 February %s" % today.year)
            
            #(but not for ranges spanning years)
            date1 = date(today.year, 12, 1)
            date2 = date(today.year+1, 3, 31)
            self.ae(humanized_date_range(date1, date2), "December %s-March %s" % (date1.year, date2.year))
            self.ae(humanized_date_range(date1, date2, imply_year=False), "December %s-March %s" % (date1.year, date2.year))
          
            #And if it's the whole month range in this year, all you need is the month name.
            date1 = date(today.year, today.month, 1)
            date2 = date(today.year, today.month, days_in_month(today))
            self.ae(humanized_date_range(date1, date2), today.strftime("%B"))
            self.ae(humanized_date_range(date1, date2, imply_year=False), "%s %s" % (today.strftime("%B"), today.year))
            date1 = date(today.year, today.month-1, 1)
            date2 = date(today.year, today.month, days_in_month(today))
            self.ae(humanized_date_range(date1, date2), "%s-%s" % (date1.strftime("%B"), date2.strftime("%B")))
            self.ae(humanized_date_range(date1, date2, imply_year=False), "%s-%s %s" % (date1.strftime("%B"), date2.strftime("%B"), today.year))

            #(don't omit this year if the range is the whole year)
            date1 = date(today.year, 1, 1)
            date2 = date(today.year, 12, 31)
            self.ae(humanized_date_range(date1, date2), "%d" % today.year)
            self.ae(humanized_date_range(date1, date2, imply_year=False), "%d" % today.year)
        
    unittest.main()