import csv

all_items = {}

with open('robot.csv') as csvfile:
    data = list(csv.reader(csvfile))
    headers = data[0]
    data = data[1:]

    for row in data:
        values = dict(zip(headers, row))
        sku = values['Farnell']

        if sku == '':
            print('WARNING: No sku for %s' % values['Name'])

        if sku not in all_items:
            all_items[sku] = []

        all_items[sku].append(values)
        

with open('bom.csv', 'w') as csvfile:
    n = 0
    writer = csv.writer(csvfile)
    writer.writerow(['Item #', 'Ref', 'Qty', 'Manufacturer', 'Mfg Part #', 'Description', 'Package', 'Type', 'Instruction'])

    for sku in all_items:
        items = all_items[sku]
        n += 1
        row = []
        row.append(n)
        row.append(', '.join([v['Name'] for v in items]))
        row.append(len(items))
        row.append('')
        row.append('')
        row.append(items[0]['Value'])
        row.append('')
        row.append('')
        row.append(sku)

        writer.writerow(row)



