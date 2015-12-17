#!/usr/bin/python3

"""
mapcyclefile - a utility to modify SRCDS mapcycle files
(a.k.a. "to make up for Valve not supporting subscription ids in TF2, how terrible of them")

Sample usage to do a dry run of syncing maps from collection 454128334 (Pikachu's CSRD Maps):
mapcyclefile.py --dry-run -c 454128334 "/path/to/tf/custom/server/cfg/mapcycle.txt"

Lost?  Just do `mapcycle.py --help` for that nice help file.

Requires the requests library:
`pip3 install requests`
"""

import requests, json, argparse, os, shutil, time, itertools

def param_dict(key, values):
	''' Generates a dict with named keys "key[i]". '''
	return { '{0}[{1}]'.format(key, i): value for i, value in enumerate(values) }

def get_collection_details(collections, api_key):
	''' Returns the results of a request to Steam's ISteamRemoteStorage/GetCollectionDetails API '''
	collection_request = {
		'key': api_key,
		'format': 'json',
		'collectioncount': len(collections)
	}
	collection_request.update(param_dict('publishedfileids', collections))
	
	try:
		r = requests.post("https://api.steampowered.com/ISteamRemoteStorage/GetCollectionDetails/v1/",
				data = collection_request)
		return r.json()
	except ConnectionError:
		raise

def get_published_file_details(fileids, api_key):
	''' Returns the results of a request to Steam's ISteamRemoteStorage/GetPublishedFileDetails API '''
	published_file_details_request = {
		'itemcount': len(fileids),
		'key': api_key,
		'format': 'json'
	}
	published_file_details_request.update(param_dict('publishedfileids', fileids))
	
	try:
		r = requests.post('https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/',
				data = published_file_details_request)
		return r.json()
	except ConnectionError:
		raise

def diff(a, b):
	'''
	Returns a list of elements that are in a but not in b
	'''
	b = set(b)
	return [aa for aa in a if aa not in b]

def changes(a, b):
	'''
	Returns a list of items that have been added and removed from a and b
	'''
	return diff(a,b) + diff(b,a)

def remove_sublist(list, sublist):
	sublist_length = len(sublist)
	for index in (i for i, element in enumerate(list) if element == sublist[0]):
		if list[index:index+sublist_length] == sublist:
			del list[max(index, 0):index+sublist_length]

def add_maps(mapcycle, additional_maps, reappend_existing = False):
	if reappend_existing:
		for map in mapcycle:
			if map in additional_maps:
				mapcycle.remove(map)
		mapcycle.extend(additional_maps)
	else:
		mapcycle.extend( map for map in additional_maps if map not in mapcycle )

def add_memo(mapcycle, comment):
	comment_lines = [ '', '// ' + comment ]
	remove_sublist(mapcycle, comment_lines)
	mapcycle.extend(comment_lines)
	return mapcycle

def arg_resolve_workshop_dir(mapcyclefile):
	'''
	Returns the workshop directory, searching up the directory tree relative to the
	mapcyclefile for it.
	'''
	if mapcyclefile is not None:
		if '/tf/' in mapcyclefile:
			tf_directory_parent = mapcyclefile[0:mapcyclefile.rfind('/tf/')]
			
			tf_workshop_candidate = tf_directory_parent + '/steamapps/workshop'
			if os.path.exists(tf_workshop_candidate):
				return tf_workshop_candidate
	return None

def import_workshop_collections(mapcycle, collections, api_key, include_tags = [], exclude_tags = []):
	'''
	Takes a bunch of maps in collections and adds them to a mapcycle, filtering them depending
	on include_tags and exclude_tags.
	
	Existing workshop maps are removed (we assume only the maps in the collections should be
	added), so ensure that this is only run once.
	
	If a map contains a tag listed in exclude_tags, it is not included in the import.
	If there are any include_tags, then the imported workshop maps must have one of the tags given to be imported.
	'''
	try:
		collectiondetails = get_collection_details(collections, api_key)
	except ConnectionError:
		print("Could not get collection details.  Is Steam down?", file=sys.stderr)
		sys.exit(1)
	
	workshop_map_ids = []
	
	for collection in collectiondetails['response']['collectiondetails']:
		for publishedfile in collection['children']:
			# filetype = 0 is map?
			if publishedfile['publishedfileid'] not in workshop_map_ids and publishedfile['filetype'] == 0:
				workshop_map_ids.append(publishedfile['publishedfileid'])
	
	try:
		published_file_results = get_published_file_details(workshop_map_ids, api_key)
	except ConnectionError:
		print("Could not get Workshop map details.  Is Steam down?", file=sys.stderr)
		sys.exit(1)
	
	workshop_map_data = {}
	
	for publishedfile in published_file_results['response']['publishedfiledetails']:
		map_tags = [ tag['tag'] for tag in publishedfile['tags'] ]
		
		if any(tag in map_tags for tag in exclude_tags):
			workshop_map_ids.remove(publishedfile['publishedfileid'])
		elif len(include_tags) > 0 and not any(tag in map_tags for tag in include_tags):
			workshop_map_ids.remove(publishedfile['publishedfileid'])
		
	
	workshop_maps = [ 'workshop/{0}'.format(map) for map in workshop_map_ids ]
	existing_workshop_maps = [ map for map in mapcycle if map.startswith('workshop/') ]
	
	# Check if the list of workshop maps is different
	if len(changes(existing_workshop_maps, workshop_maps)) > 0:
		# Remove all workshop maps and add the ones we want back in.
		mapcycle = [ map for map in mapcycle if not map.startswith('workshop/') ]
		mapcycle = add_memo(mapcycle, 'Imported workshop maps')
		add_maps(mapcycle, workshop_maps, True)
	
	return mapcycle

def is_valid_map_name(map):
	return (not map.startswith('//')) and len(map) > 0

def is_workshop_short_name(map):
	return map.startswith('workshop/') and '.ugc' not in map

def list_map_prefix_duplicates(map, maplist):
	# TODO optimize this method and fix
	split_map_name = map.split('_')
	max_prefix_count = len(split_map_name)
	map_name_sections = [ map.split('_') for map in maplist if is_valid_map_name(map) and not map.startswith('workshop/') ]
	map_duplicate_prefixes = set()
	for i in range(2, max_prefix_count + 1):
		target_split_map_name = '_'.join(split_map_name[0:i])
		prefix_map_names = [ '_'.join(partial_map_name[0:i])
				for partial_map_name in map_name_sections if len(partial_map_name) > i-1 ]
		s = set()
		# I have no idea what I'm doing here, but it works!  ...ish.
		duplicates = set(map_prefix for map_prefix in prefix_map_names
				if map_prefix == target_split_map_name or s.add(map_prefix))
		map_duplicate_prefixes.update(duplicates)
	
	if len(map_duplicate_prefixes) > 0:
		print(map_duplicate_prefixes)
	return map_duplicate_prefixes

def list_map_shared_prefixes(mapcycle):
	'''
	Returns a dict containing map prefixes pointing to lists of map names sharing that prefix.
	Useful to see if you have multiple versions of the same non-workshop map.
	'''
	# TODO initally exclude stock maps?
	map_names = [ map for map in mapcycle
			if not (map.startswith('//') or map.startswith('workshop/')) and len(map) > 0 ]
	
	max_prefix_count = max([ map.count('_') for map in map_names ])
	map_name_sections = [ map.split('_') for map in map_names ]
	
	map_duplicate_prefixes = set()
	
	# Start at 2 so we don't match gamemode prefix
	for i in range(2, max_prefix_count + 1):
		# Don't consider map name prefixes duplicates if not matching number of underscores?
		#     - if len(partial_map_name) > i-1
		# That may be problematic if you want to consider "X" and "X_final" as duplicates
		prefix_map_names = [ '_'.join(partial_map_name[0:i])
				for partial_map_name in map_name_sections if len(partial_map_name) > i-1 ]
		s = set()
		duplicates = set(map for map in prefix_map_names if map in s or s.add(map))
		map_duplicate_prefixes.update(duplicates)
	
	for x, y in itertools.combinations(map_names, 2):
		prefix = min(x, y)
		map = max(x, y)
		if map.startswith(prefix):
			map_duplicate_prefixes.add(prefix)
	
	return {
		map_prefix: [ map for map in map_names if map.startswith(map_prefix) ]
		for map_prefix in map_duplicate_prefixes
	}

def list_possible_workshop_duplicates(mapcycle, workshop_directory):
	'''
	Returns a list of non-workshop maps that share base filenames with workshop maps, or with
	another map in the mapcycle.
	
	This only runs on maps that have been downloaded.
	
	This is useful to see if you forgot to remove a non-workshop map after adding its workshop
	version, or if you have another version of the map in the mapcycle.
	'''
	if workshop_directory is not None:
		possible_dupes = {}
		
		workshop_map_names = {}
		workshop_map_directory = workshop_directory + '/content/440'
		workshop_map_ids = [ map.lstrip('workshop/') for map in mapcycle if map.startswith('workshop/') ]
		
		# TODO fix for long-name support
		for i in os.listdir(workshop_map_directory):
			if i in workshop_map_ids:
				workshop_map_path = workshop_map_directory + os.sep + i
				for f in os.listdir(workshop_map_path):
					workshop_map_names[f.rstrip('.bsp')] = i
		
		# TODO make sure this actually works
		for map, id in workshop_map_names.items():
			dupes = list_map_prefix_duplicates(map, mapcycle)
			if len(dupes) > 0:
				possible_dupes['workshop/{}'.format(id)] = list(dupes)
		return possible_dupes
	else:
		return {}

def get_workshop_displayname(map_id, workshop_directory):
	workshop_map_directory = workshop_directory + '/content/440'
	workshop_map_path = workshop_map_directory + '/' + str(map_id)
	if os.path.exists(workshop_map_path):
		for f in os.listdir(workshop_map_path):
			return f.rstrip('.bsp')
	return None

def resolve_workshop_shortname(workshop_map, workshop_directory):
	'''
	Attempts to resolve a shorthand workshop name (e.g. "workshop/454796385") into the full name
	(e.g. "workshop/koth_octothorpe_classic_beta01.ugc454796385").
	
	For this to work, the map must be available in the game's workshop directory.
	If the map name cannot be resolved, then workshop_map is returned.
	
	Fun fact:  TF2 doesn't seem to care about the long workshop name, as long as the ID is intact.
	It *should* update to the latest version while tracking.
	'''
	if is_workshop_short_name(workshop_map):
		map_id = int(workshop_map.lstrip('workshop/'))
		display_name = get_workshop_displayname(map_id, workshop_directory)
		if display_name is not None:
			return 'workshop/{}.ugc{}'.format(display_name, str(map_id))
	return workshop_map

def get_file_as_lines(filename):
	'''
	Read filename into a list, stripping out newline characters.
	If file doesn't exist, return empty list.
	'''
	if os.path.isfile(filename):
		with open(filename) as f:
			lines = f.readlines()
	else:
		lines = []
	
	return [ line.rstrip('\n') for line in lines ]
	
def main(args):
	collections = args.collection
	api_key = args.api_key
	
	mapcycle = get_file_as_lines(args.mapcycle)
	new_mapcycle = mapcycle[:]
	
	if collections is not None and len(collections) > 0:
		new_mapcycle = import_workshop_collections(mapcycle[:], collections, api_key, include_tags = args.include_tags,
				exclude_tags = args.exclude_tags)
	
	if args.long_workshop_names and args.workshop_dir is not None:
		for i, map in enumerate(new_mapcycle):
			if is_workshop_short_name(map):
				new_mapcycle[i] = resolve_workshop_shortname(map, args.workshop_dir)
	
	if args.list_duplicates:
		possible_dupes_dict = list_map_shared_prefixes(new_mapcycle[:])
		possible_dupes_dict.update(list_possible_workshop_duplicates(new_mapcycle[:], args.workshop_dir))
		if len(possible_dupes_dict) > 0:
			for prefix, dupes in possible_dupes_dict.items():
				print('- {} has {} potential copies: {}'.format(prefix, len(dupes), dupes))
			print('')
	
	# Done processing map modifications -- write it back out if necessary.
	mapcycle_filename = os.path.basename(args.mapcycle)
	
	additions = len(diff(new_mapcycle, mapcycle))
	deletions = len(diff(mapcycle, new_mapcycle))
	if additions + deletions > 0:
		if args.dry_run:
			print( ("{} has not been modified due to being a dry run.  "
					"The following changes (+{}, -{}) would have been made:").format(mapcycle_filename, additions, deletions) )
		else:
			if args.backup:
				# Assumed to be a /cfg/ directory.  Hopefully there's no instances where it's not?
				mapcycle_backup_dir = os.path.dirname(args.mapcycle) + '/mapcycle_backups'
				if not os.path.exists(mapcycle_backup_dir):
					os.makedirs(mapcycle_backup_dir)
				
				if os.path.isfile(args.mapcycle):
					mapcycle_backup_filename = list(os.path.splitext(os.path.basename(args.mapcycle)))
					mapcycle_backup_filename[0] = '{0}_{1}'.format(mapcycle_backup_filename[0], time.strftime('%Y%m%d_%H%M%S'))
					mapcycle_backup_path = mapcycle_backup_dir + '/' + ''.join(mapcycle_backup_filename)
					
					shutil.copyfile(args.mapcycle, mapcycle_backup_path)
					print('Copied mapcycle {} to backup at {}'.format(mapcycle_filename, mapcycle_backup_path))
			
			with open(args.mapcycle, 'w') as f:
				f.writelines( '{}\n'.format(line) for line in new_mapcycle )
			print('Made the following changes (+{}, -{}) to {}:'.format(additions, deletions, mapcycle_filename))
		
		# Output added and removed maps in a clean format.
		added_maps = [ map for map in diff(new_mapcycle, mapcycle) if is_valid_map_name(map) ]
		if len(added_maps) > 0:
			print('+ {}'.format(added_maps))
		
		removed_maps = [ map for map in diff(mapcycle, new_mapcycle) if is_valid_map_name(map) ]
		if len(removed_maps) > 0:
			print('- {}'.format(removed_maps))
		
		if len(added_maps) + len(removed_maps) == 0: print('+/- []')
	else:
		if not args.quiet:
			print('No changed workshop maps.  No modification has been made to {}.'.format(mapcycle_filename))

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Modifies Source Engine Dedicated Server mapcycle files.',
			usage='%(prog)s [options] mapcycle')
	
	parser.add_argument('--dry-run', action='store_true', help='do not write modified mapcycle back, only display changes')
	
	parser.add_argument('--api-key', nargs=1, metavar='KEY',
			help='a Steam WebAPI key (will fall back to environment\'s STEAM_API_KEY otherwise)')
	parser.add_argument('-c', '--collection', metavar='ID', action='append',
			help='a Steam Workshop map collection to retrieve maps from')
	
	parser.add_argument('--backup', action='store_true', help='save a backup copy of the mapcycle on successful change')
	
	parser.add_argument('--include-workshop-tag', metavar='TAG', action='append',
			help='allow workshop entries that contain one or more of these tags', dest='include_tags')
	parser.add_argument('--exclude-workshop-tag', metavar='TAG', action='append',
			help='ignore workshop entries that include this tag', dest='exclude_tags')
	
	parser.add_argument('-q', '--quiet', action='store_true', help='does not output informational text if nothing changed')
	
	parser.add_argument('--workshop-dir', metavar='DIR',
			help=('the game\'s workshop directory (e.g., /tf/../steamapps/workshop);'
			'will attempt to autodetect based off of input config if not supplied'))
	
	parser.add_argument('--list-duplicates', action='store_true', help='list maps that share prefixes (possible duplicates)')
	
	parser.add_argument('--long-workshop-names', action='store_true', help='use full workshop map names for downloaded maps')
	
	parser.add_argument('mapcycle', help='the mapcycle file to be modified')
	
	args = parser.parse_args()
	
	args.api_key = args.api_key or os.environ.get('STEAM_API_KEY')
	
	if args.api_key is None:
		raise ValueError('no Steam WebAPI key provided: add a STEAM_API_KEY environment variable or run with --api-key')
	
	if args.dry_run:
		if args.backup:
			print('Ignoring --backup flag as we are doing a dry run.')
		if args.quiet:
			print('Ignoring --quiet flag as we are doing a dry run.')
	
	args.include_tags = args.include_tags or []
	args.exclude_tags = args.exclude_tags or []
	
	if args.workshop_dir is None and args.mapcycle is not None:
		args.workshop_dir = arg_resolve_workshop_dir(args.mapcycle)
		if not args.quiet and args.workshop_dir is not None:
			# TODO add verbosity level
			print('Using {} as the workshop directory.'.format(args.workshop_dir))
	
	main(args)
