import re
import random
import urllib
import urllib2 as urllib
import urlparse
import json
from datetime import datetime
from PIL import Image
from cStringIO import StringIO

VERSION_NO = '1.2013.06.02.1'

def any(s):
    for v in s:
        if v:
            return True
    return False

def capitalize(line):
    return ' '.join([s[0].upper() + s[1:] for s in line.split(' ')])

def tagAleadyExists(tag,metadata):
    for t in metadata.genres:
        if t.lower() == tag.lower():
            return True
    return False

def posterAlreadyExists(posterUrl,metadata):
    for p in metadata.posters.keys():
        Log(p.lower())
        if p.lower() == posterUrl.lower():
            Log("Found " + posterUrl + " in posters collection")
            return True

    for p in metadata.art.keys():
        if p.lower() == posterUrl.lower():
            return True
    return False

def Start():
    HTTP.CacheTime = CACHE_1DAY

class EXCAgent(Agent.Movies):
    name = 'Naughty America'
    languages = [Locale.Language.English]
    accepts_from = ['com.plexapp.agents.localmedia']
    primary_provider = True

    def search(self, results, media, lang):
        
        title = media.name
        if media.primary_metadata is not None:
            title = media.primary_metadata.title

        Log('*******MEDIA TITLE****** ' + str(title))

        # Search for year
        year = media.year
        if media.primary_metadata is not None:
            year = media.primary_metadata.year

        trimmedTitle = title.split(" & ")
        temp = trimmedTitle[0]
        if(',' in temp):
            temp = temp.split(',')[0]

        encodedTitle = temp.replace(" ","-")
        searchResults = HTML.ElementFromURL('http://tour.naughtyamerica.com/search?term=' + encodedTitle.lower())

        for searchResult in searchResults.xpath('//div[@class="grid-item"]'):
            link = searchResult.xpath('.//a')[0]
            titleNoFormatting = link.get('title')
            curID = link.get('href').replace('/','_').split("?")[0]
            score = 100 - Util.LevenshteinDistance(title.lower(), titleNoFormatting.lower())             
            results.Append(MetadataSearchResult(id = curID, name = titleNoFormatting, score = score, lang = lang))

        for page in searchResults.xpath('//ul[@class="pagination"]//a'):
            url = page.get('href')
            Log(url)
            addPage = HTML.ElementFromURL(url)
            for searchResult in addPage.xpath('//div[@class="grid-item"]'):
                link = searchResult.xpath('.//a')[0]
                titleNoFormatting = link.get('title')
                curID = link.get('href').replace('/','_').split("?")[0]
                score = 100 - Util.LevenshteinDistance(title.lower(), titleNoFormatting.lower())             
                results.Append(MetadataSearchResult(id = curID, name = titleNoFormatting, score = score, lang = lang))
        
        results.Sort('score', descending=True)            

    def update(self, metadata, media, lang):

        Log('******UPDATE CALLED*******')
        metadata.studio = 'Naughty America'
        url = str(metadata.id).replace('_','/')
        detailsPageElements = HTML.ElementFromURL(url)
        Log(url);
        # Summary
        paragraph = detailsPageElements.xpath('//p[@class="synopsis_txt"]')[0].text_content()
        metadata.summary = paragraph.replace('&13;', '').strip(' \t\n\r"') + "\n\n"
        metadata.tagline = detailsPageElements.xpath('//div[@id="synopsis"]//h1')[0].text_content().split(' in ')[1]
        metadata.title = detailsPageElements.xpath('//div[@id="synopsis"]//h1')[0].text_content()

        # Genres
        metadata.genres.clear()
        genres = detailsPageElements.xpath('//a[contains(@class,"cat-tag")]')
        genreFilter=[]
        if Prefs["excludegenre"] is not None:
            genreFilter = Prefs["excludegenre"].lower().split(';')

        genreMaps=[]
        genreMapsDict = {}

        if Prefs["tagmapping"] is not None:
            genreMaps = Prefs["tagmapping"].split(';')
            for mapping in genreMaps:
                keyVal = mapping.split("=")
                genreMapsDict[keyVal[0]] = keyVal[1].lower()
        else:
            genreMapsDict = None
        
        if len(genres) > 0:
            for genreLink in genres:
                genreName = genreLink.text_content().strip('\n').lower()          
                if any(genreName in g for g in genreFilter) == False:
                    if genreMapsDict is not None:
                        if genreName in genreMapsDict:
                            Log(genreName + " in genre map will add " + genreMapsDict[genreName])
                            if not tagAleadyExists(genreMapsDict[genreName],metadata):
                                metadata.genres.add(capitalize(genreMapsDict[genreName]))
                        else:
                            Log(genreName + " not in genre map")
                            if not tagAleadyExists(genreName,metadata):
                                metadata.genres.add(capitalize(genreName))
                    else:   
                        metadata.genres.add(capitalize(genreName))

        date = detailsPageElements.xpath('//p[@class="scenedate"]')[0].text_content().split(":")[1].strip()
        date_object = datetime.strptime(date, '%b %d, %Y')
        metadata.originally_available_at = date_object
        metadata.year = metadata.originally_available_at.year

        rating = detailsPageElements.xpath('//*[@id="scene-info"]/div[3]/p')[0].text_content().replace('Scene Rating: ','')
        metadata.rating = float(rating)

        # Starring/Collection
        # Create a string array to hold actors
        maleActors=[]

        # Refresh the cache every 50th query
        if('cache_count' not in Dict):
            Dict['cache_count'] = 0
            Dict.Save()
        else:
            cache_count = float(Dict['cache_count'])
            if(cache_count == 50):
                Log(str(cache_count))
                Dict.Reset()
            else:
                Dict['cache_count'] = str(cache_count + 1)
                Dict.Save()
                Log(str(cache_count))
        
        if('actors' not in Dict):
            Log('******NOT IN DICT******')
            maleActorHtml = None
            maleActorHtml = HTML.ElementFromURL('http://www.data18.com/pornstars/male.html')

            # Add missing actors
            for actor in maleActorHtml.xpath('//span[@class="gen11"]//a'):
                # itemString = actor.text_content()
                # actorArray = itemString.split("(")
                try:
                    # Add item to array
                    # actor = actorArray[0].strip()
                    maleActors.append(actor.text_content())
                except: pass
            Dict['actors'] = maleActors
            Dict.Save()
        else:
            Log('******IN DICT******')
            maleActors = Dict['actors']

        if Prefs['excludeactor'] is not None:
            addActors = Prefs['excludeactor'].split(';')
            for a in addActors:
                maleActors.append(a)

        metadata.roles.clear()
        metadata.collections.clear()
        
        #starring = None
        starring = detailsPageElements.xpath('//div[@id="scene-info"]//p[1]//a')
        for member in starring:
            # Check if member exists in the maleActors list as either a string or substring
            if any(member.text_content().strip() in m for m in maleActors) == False:
                role = metadata.roles.new()
                # Add to actor and collection
                role.actor = member.text_content().strip()
                metadata.collections.add(member.text_content().strip())

        #Posters
        i = 1

        for poster in detailsPageElements.xpath('//a[contains(@class,"fancybox")]'):
            posterUrl = poster.get('href').strip()
            thumbUrl = poster.xpath('.//img')[0].get('src')
            if not posterAlreadyExists(posterUrl,metadata):
                Log("media doesnt exist in key")
                if not "vert_scene" in str(posterUrl):
                    Log("ADDED ART")
                    metadata.art[posterUrl] = Proxy.Preview(HTTP.Request(thumbUrl, headers={'Referer': 'http://www.google.com'}).content, sort_order = i)
                else:
                    Log("ADDED POSTER")
                    metadata.posters[posterUrl] = Proxy.Preview(HTTP.Request(thumbUrl, headers={'Referer': 'http://www.google.com'}).content, sort_order = i)
            i += 1
