from webapp import keep_alive
import time
import discord
import json
import aiohttp
import traceback
import re
from datetime import datetime
from croniter import croniter
import os
from pytz import timezone
import asyncio
from discord import Intents
from discord.ext import commands

intents = discord.Intents.default()
intents.messages = True
intents.members = True
client = commands.Bot(command_prefix='up!', intents=intents)
client.activity = discord.Activity (type=discord.ActivityType.competing, name="With traditional UptimeRobot")

keep_alive()

# Define a function to ping a website with a given method and time interval
async def ping_website(url, method, time_interval, ping_count, user_id, website):
    # Load the last_status value from the ls.json file
    with open('ls.json', 'r') as f:
        ls_data = json.load(f)
    user_ls_data = ls_data.get(str(user_id), {})
    monitor_ls_data = user_ls_data.get(website['index'], {})
    last_status = monitor_ls_data.get('last_status', None)

    # Load the error_count and ping_count values from the an_data.json file
    with open('an_data.json', 'r') as f:
        an_data = json.load(f)
    user_an_data = an_data.get(str(user_id), {})
    monitor_an_data = user_an_data.get(website['index'], {})
    error_count = monitor_an_data.get('error_count', 0)
    ping_count = monitor_an_data.get('ping_count', 0)

    # Set the time_interval attribute on the current task
    asyncio.current_task().time_interval = time_interval

    async with aiohttp.ClientSession() as session:
        while True:
            start_time = time.time()
            try:
                if method == 'HEAD':
                    response = await session.head(url)
                elif method == 'GET':
                    response = await session.get(url)
                elif method == 'POST':
                    response = await session.post(url)
                response_time = round((time.time() - start_time) * 1000)
                now = datetime.now(timezone('Asia/Kolkata'))
                date_time = now.strftime("%d/%m/%y @ %I:%M %p")
                ping_count += 1
                log = f'{url}: {response.status} | Pinged on {date_time} (IST) | Ping count: {ping_count} | Response time: {response_time}ms'
                print(log)

                # Update the analytics data for this monitor
                with open('analytics.json', 'r') as f:
                    analytics = json.load(f)
                user_analytics = analytics.get(str(user_id), {})
                monitor_analytics = user_analytics.get(website['index'], {})
                response_times = monitor_analytics.get('response_times', [])
                response_times.append(response_time)
                if len(response_times) > 15:
                    response_times.pop(0)
                average_response_time = round(sum(response_times) / len(response_times), 2)
                monitor_analytics['average_response_time'] = average_response_time
                error_rate = round(error_count / ping_count * 100, 2)
                monitor_analytics['error_rate'] = f'{error_rate}%'
                uptime_percentage = round((ping_count - error_count) / ping_count * 100, 2)
                monitor_analytics['uptime_percentage'] = f'{uptime_percentage}%'
                user_analytics[website['index']] = monitor_analytics
                analytics[str(user_id)] = user_analytics
                with open('analytics.json', 'w') as f:
                    json.dump(analytics, f)

                # Update the ls.json file with the last ping status
                status = 'UP' if response.status == 200 else 'DOWN'
                user_ls_data = ls_data.setdefault(str(user_id), {})
                monitor_ls_data = user_ls_data.setdefault(website['index'], {})
                monitor_ls_data['last_status'] = status
                with open('ls.json', 'w') as f:
                    json.dump(ls_data, f)

                # Check if the status of the website has changed
                if status != last_status and last_status is not None:
                    # Check if alerts are turned on for this website
                    with open('alerts.json', 'r') as f:
                        alerts = json.load(f)
                    user_alerts = alerts.get(str(user_id), {})
                    alerts_on = user_alerts.get(website['index'], True)
                    if alerts_on:
                        user = client.get_user(int(user_id))
                        if status == 'UP':
                            embed = discord.Embed(title='WEBSITE UP', description=f'Website {website["index"]} is up.', color=0x00ff00)
                            embed.set_footer(text='Website up reminder || UpTimeRobot alert system')
                            await user.send(embed=embed)
                        else:
                            embed = discord.Embed(title='WEBSITE DOWN', description=f'Website {website["index"]} is down.', color=0xff0000)
                            embed.set_footer(text='Website down reminder || UpTimeRobot alert system')
                            await user.send(embed=embed)
                            error_count += 1
                    last_status = status

                # Store information about the monitor status change in the history.json file
                with open('history.json', 'r') as f:
                    history = json.load(f)
                user_history = history.get(str(user_id), {})
                monitor_history = user_history.get(website['index'], [])
                monitor_history.append({'time': date_time, 'status': status})
                if len(monitor_history) > 15:
                    monitor_history.pop(0)
                user_history[website['index']] = monitor_history
                history[str(user_id)] = user_history
                with open('history.json', 'w') as f:
                    json.dump(history, f)

                # Store the last ping time and response status in the websites.json file
                with open('websites.json', 'r') as f:
                    websites = json.load(f)
                    for user_id, user_websites in websites.items():
                        for website in user_websites:
                            if website['url'] == url:
                                website['last_ping_time'] = date_time
                                website['response_status'] = f'{response.status} {response.reason}'
                                break
                with open('websites.json', 'w') as f:
                    json.dump(websites, f)

                # Save the error_count and ping_count values to the an_data.json file
                monitor_an_data['error_count'] = error_count
                monitor_an_data['ping_count'] = ping_count
                user_an_data[website['index']] = monitor_an_data
                an_data[str(user_id)] = user_an_data
                with open('an_data.json', 'w') as f:
                    json.dump(an_data, f)

            except Exception as e:
                print(f'Error pinging {url}: {e}')

            # Wait for the time interval before pinging again
            await asyncio.sleep(time_interval)


async def send_requests():
    ping_count = {}

    # Create a dictionary to store the tasks for each website
    tasks = {}

    while True:

        # Check if there are any new websites added or removed from the file
        with open('websites.json', 'r') as f:
            websites = json.load(f)

            # Loop through the websites for each user
            for user_id, user_websites in websites.items():

                # Loop through the websites for each user
                for website in user_websites:

                    # Get the url, method and time interval of the website
                    url = website['url']
                    method = website['method']
                    time_interval = website['time_interval']

                    # Check if the monitor is scheduled to run
                    with open('schedules.json', 'r') as f:
                        schedules = json.load(f)
                    user_schedules = schedules.get(user_id, {})
                    schedule = user_schedules.get(website.get('index', None))
                    if schedule:
                        now = datetime.now(timezone('Asia/Kolkata'))
                        iter = croniter(schedule, now)
                        next_run = iter.get_next(datetime)
                        if now < next_run:
                            continue

                    # If the website is stopped, cancel its task if it exists
                    if 'stopped' in website and website['stopped']:
                        if url in tasks:
                            tasks[url].cancel()
                            del tasks[url]
                        continue

                    # If the url is not in the tasks dictionary, create a new task for it
                    if url not in tasks:
                        tasks[url] = asyncio.create_task(ping_website(url, method, time_interval, ping_count, user_id, website))

                    # If the url is in the tasks dictionary, but the time interval has changed, cancel the old task and create a new one
                    elif tasks[url].time_interval != time_interval:
                        tasks[url].cancel()
                        tasks[url] = asyncio.create_task(ping_website(url, method, time_interval, ping_count, user_id, website))

            # Loop through the tasks dictionary and cancel any task that is not in the file anymore
            for url, task in list(tasks.items()):
                if not any(url == website['url'] for user_websites in websites.values() for website in user_websites):
                    task.cancel()
                    del tasks[url]

        # Wait for 5 seconds before checking the file again
        await asyncio.sleep(5)



client.remove_command('help')

@client.command()
async def help(ctx, command=None):
    # If no command is specified, send the general help message
    if command is None:
        embed = discord.Embed(title='Help', description='This is a bot that monitors websites and sends requests to them periodically.', color=0x00ff00)
        embed.add_field(name='up!monitor <website>', value='Add a website to monitor. You will be asked to choose a method (HEAD, GET or POST) and a time interval for pinging the website.', inline=False)
        embed.add_field(name='up!remove <index>', value='Remove a website from monitoring by its index. Use up!stats to view your monitored websites and their indices.', inline=False)
        embed.add_field(name='up!start <index>', value='Start monitoring a website that was stopped. You need to provide the index of the website. Use up!stats to view your monitored websites and their indices.', inline=False)
        embed.add_field(name='up!stop <index>', value='Stop monitoring a website. You need to provide the index of the website. Use up!stats to view your monitored websites and their indices.', inline=False)
        embed.add_field(name='up!stats', value='View the statistics of your monitored websites, such as the last ping time and response status. The statistics will be sent to your DMs.', inline=False)
        embed.add_field(name='up!alert', value='Turn alerts on or off for a specific website. You will be asked to choose a website by its index and whether you want to turn alerts on or off.', inline=False)
        embed.add_field(name='up!schedule <index> <schedule>', value='Set a schedule for a specific monitor using a cron expression. You need to provide the index of the monitor and the cron expression.', inline=False)
        embed.add_field(name='up!history <index>', value='View the history of a specific monitor. You need to provide the index of the monitor.', inline=False)
        embed.add_field(name='up!analytics <index>', value='View the analytics of a specific monitor, such as response times, error rate, and uptime percentage. You need to provide the index of the monitor.', inline=False)
        embed.add_field(name='up!help [command]', value='Get help on how to use this bot or a specific command.', inline=False)
        embed.set_footer(text='up!help')
        await ctx.send(embed=embed)

    # If a command is specified, send the help message for that command
    else:
        # Check if the command is valid
        if command in ['monitor', 'remove', 'start', 'stop', 'stats', 'alert', 'schedule', 'history', 'analytics', 'help']:
            # Send the help message for the monitor command
            if command == 'monitor':
                embed = discord.Embed(title='Help: monitor', description='Add a website to monitor. You will be asked to choose a method (HEAD, GET or POST) and a time interval for pinging the website (minimum 1 minute).', color=0x00ff00)
                embed.add_field(name='Usage', value='up!monitor <website>', inline=False)
                embed.add_field(name='Example', value='up!monitor https://example.com', inline=False)
                embed.set_footer(text='up!help monitor')
                await ctx.send(embed=embed)

            # Send the help message for the remove command
            elif command == 'remove':
                embed = discord.Embed(title='Help: remove', description='Remove a website from monitoring by its index. Use up!stats to view your monitored websites and their indices.', color=0x00ff00)
                embed.add_field(name='Usage', value='up!remove <index>', inline=False)
                embed.add_field(name='Example', value='up!remove 1', inline=False)
                embed.set_footer(text='up!help remove')
                await ctx.send(embed=embed)

            # Send the help message for the start command
            elif command == 'start':
                embed = discord.Embed(title='Help: start', description='Start monitoring a website that was stopped. You need to provide the index of the website. Use up!stats to view your monitored websites and their indices.', color=0x00ff00)
                embed.add_field(name='Usage', value='up!start <index>', inline=False)
                embed.add_field(name='Example', value='up!start 1', inline=False)
                embed.set_footer(text='up!help start')
                await ctx.send(embed=embed)

            # Send the help message for the stop command
            elif command == 'stop':
                embed = discord.Embed(title='Help: stop', description='Stop monitoring a website. You need to provide the index of the website. Use up!stats to view your monitored websites and their indices.', color=0x00ff00)
                embed.add_field(name='Usage', value='up!stop <index>', inline=False)
                embed.add_field(name='Example', value='up!stop 1', inline=False)
                embed.set_footer(text='up!help stop')
                await ctx.send(embed=embed)

            # Send the help message for the stats command
            elif command == 'stats':
                embed = discord.Embed(title='Help: stats', description='View the statistics of your monitored websites, such as the last ping time and response status. The statistics will be sent to your DMs.', color=0x00ff00)
                embed.add_field(name='Usage', value='up!stats', inline=False)
                embed.set_footer(text='up!help stats')
                await ctx.send(embed=embed)

            # Send the help message for the alert command
            elif command == 'alert':
                embed = discord.Embed(title='Help: alert', description='Turn alerts on or off for a specific website. You will be asked to choose a website by its index and whether you want to turn alerts on or off.', color=0x00ff00)
                embed.add_field(name='Usage', value='up!alert', inline=False)
                embed.set_footer(text='up!help alert')
                await ctx.send(embed=embed)

            # Send the help message for the schedule command
            elif command == 'schedule':
                embed = discord.Embed(title='Help: schedule', description='Set a schedule for a specific monitor using a cron expression. You need to provide the index of the monitor and the cron expression.', color=0x00ff00)
                embed.add_field(name='Usage', value='up!schedule <index> <schedule>', inline=False)
                embed.add_field(name='Example', value='up!schedule 1 */5 * * * *', inline=False)
                embed.set_footer(text='up!help schedule')
                await ctx.send(embed=embed)

            # Send the help message for the history command
            elif command == 'history':
                embed = discord.Embed(title='Help: history', description='View the history of a specific monitor. You need to provide the index of the monitor.', color=0x00ff00)
                embed.add_field(name='Usage', value='up!history <index>', inline=False)
                embed.add_field(name='Example', value='up!history 1', inline=False)
                embed.set_footer(text='up!help history')
                await ctx.send(embed=embed)

            # Send the help message for the analytics command
            elif command == 'analytics':
                embed = discord.Embed(title='Help: analytics', description='View the analytics of a specific monitor, such as response times, error rate, and uptime percentage. You need to provide the index of the monitor.', color=0x00ff00)
                embed.add_field(name='Usage', value='up!analytics <index>', inline=False)
                embed.add_field(name='Example', value='up!analytics 1', inline=False)
                embed.set_footer(text='up!help analytics')
                await ctx.send(embed=embed)

            # Send the help message for the help command
            elif command == 'help':
                embed = discord.Embed(title='Help: help', description='Get help on how to use this bot or a specific command.', color=0x00ff00)
                embed.add_field(name='Usage', value='up!help [command]', inline=False)
                embed.add_field(name='Example', value='up!help monitor', inline=False)
                embed.set_footer(text='up!help help')
                await ctx.send(embed=embed)

        # If the command is not valid, send an error message
        else:
            embed = discord.Embed(title='Error', description=f'Invalid command: {command}', color=0xff0000)
            embed.set_footer(text='up!help')
            await ctx.send(embed=embed)


@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    await send_requests()

@client.command()
async def start(ctx, index: int = None):
    if index is None:
        embed = discord.Embed(title='Error', description='Please include the index of the website to start. Example: up!start 1\nIf you do not know the index, use the up!stats command to view your monitored websites.', color=0xff0000)
        embed.set_footer(text='up!start')
        await ctx.send(embed=embed)
        return
    with open('websites.json', 'r') as f:
        websites = json.load(f)
    user_websites = websites.get(str(ctx.author.id), [])
    if not user_websites:
        embed = discord.Embed(title='Error', description='You have not added any websites to monitor', color=0xff0000)
        embed.set_footer(text='up!start')
        await ctx.send(embed=embed)
        return
    if index < 1 or index > len(user_websites):
        embed = discord.Embed(title='Error', description=f'Invalid index. Please enter a number between 1 and {len(user_websites)}\nIf you do not know the index, use the up!stats command to view your monitored websites.', color=0xff0000)
        embed.set_footer(text='up!start')
        await ctx.send(embed=embed)
        return
    website = user_websites[index - 1]
    if 'stopped' in website and website['stopped']:
        website['stopped'] = False
        websites[str(ctx.author.id)] = user_websites
        with open('websites.json', 'w') as f:
            json.dump(websites, f)
        embed = discord.Embed(title='Success', description=f'Website {index} started', color=0x00ff00)
        embed.set_footer(text='up!start')
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(title='Error', description=f'Website {index} is already started', color=0xff0000)
        embed.set_footer(text='up!start')
        await ctx.send(embed=embed)

@client.command()
async def stop(ctx, index: int = None):
    if index is None:
        embed = discord.Embed(title='Error', description='Please include the index of the website to stop. Example: up!stop 1\nIf you do not know the index, use the up!stats command to view your monitored websites.', color=0xff0000)
        embed.set_footer(text='up!stop')
        await ctx.send(embed=embed)
        return
    with open('websites.json', 'r') as f:
        websites = json.load(f)
    user_websites = websites.get(str(ctx.author.id), [])
    if not user_websites:
        embed = discord.Embed(title='Error', description='You have not added any websites to monitor', color=0xff0000)
        embed.set_footer(text='up!stop')
        await ctx.send(embed=embed)
        return
    if index < 1 or index > len(user_websites):
        embed = discord.Embed(title='Error', description=f'Invalid index. Please enter a number between 1 and {len(user_websites)}\nIf you do not know the index, use the up!stats command to view your monitored websites.', color=0xff0000)
        embed.set_footer(text='up!stop')
        await ctx.send(embed=embed)
        return
    website = user_websites[index - 1]
    if 'stopped' not in website or not website['stopped']:
        website['stopped'] = True
        websites[str(ctx.author.id)] = user_websites
        with open('websites.json', 'w') as f:
            json.dump(websites, f)
        embed = discord.Embed(title='Success', description=f'Website {index} stopped', color=0x00ff00)
        embed.set_footer(text='up!stop')
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(title='Error', description=f'Website {index} is already stopped', color=0xff0000)
        embed.set_footer(text='up!stop')
        await ctx.send(embed=embed)


@client.command()
async def alert(ctx):
    # Check if the user has any websites to monitor
    with open('websites.json', 'r') as f:
        websites = json.load(f)
    user_websites = websites.get(str(ctx.author.id), [])
    if not user_websites:
        embed = discord.Embed(title='Error', description='You do not have any websites to monitor.', color=0xff0000)
        embed.set_footer(text='up!alert')
        await ctx.send(embed=embed)
        return

    # Prompt the user to choose a website
    embed = discord.Embed(title='Website', description='Which website do you want to set an alert for? Reply with your website index. If you don\'t know the index, please use up!stats.', color=0x00ff00)
    embed.set_footer(text='up!alert')
    await ctx.send(embed=embed)
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()
    try:
        response = await client.wait_for('message', check=check, timeout=30.0)
    except asyncio.TimeoutError:
        embed = discord.Embed(title='Error', description='Sorry, you took too long to respond.', color=0xff0000)
        embed.set_footer(text='up!alert')
        await ctx.send(embed=embed)
        return
    website_index = int(response.content) - 1
    if not (0 <= website_index < len(user_websites)):
        embed = discord.Embed(title='Error', description=f'Please enter a valid website index.', color=0xff0000)
        embed.set_footer(text='up!alert')
        await ctx.send(embed=embed)
        return
    website = user_websites[website_index]

    # Check if alerts are already on or off for this website
    with open('alerts.json', 'r') as f:
        alerts = json.load(f)
    user_alerts = alerts.get(str(ctx.author.id), {})
    alerts_on = user_alerts.get(website['index'], True)

    # Prompt the user to turn alerts on or off
    embed = discord.Embed(title='Alerts', description=f'Do you want to turn alerts on or off for this website?', color=0x00ff00)
    embed.set_footer(text='up!alert')
    await ctx.send(embed=embed)
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content in ['on', 'off']
    try:
        response = await client.wait_for('message', check=check, timeout=30.0)
    except asyncio.TimeoutError:
        embed = discord.Embed(title='Error', description='Sorry, you took too long to respond.', color=0xff0000)
        embed.set_footer(text='up!alert')
        await ctx.send(embed=embed)
        return

    # Check if the user is trying to turn on or off alerts for a website that already has alerts turned on or off, respectively
    if (response.content == 'on' and alerts_on) or (response.content == 'off' and not alerts_on):
        embed = discord.Embed(title='Error', description=f'Website {website["index"]} already has its alerts turned {"on" if alerts_on else "off"}.', color=0xff0000)
        embed.set_footer(text='up!alert')
        await ctx.send(embed=embed)
        return

    # Update the alerts.json file with the new alert setting
    user_alerts[website['index']] = response.content == 'on'
    alerts[str(ctx.author.id)] = user_alerts
    with open('alerts.json', 'w') as f:
        json.dump(alerts, f)

    # Send a success message
    embed = discord.Embed(title='Success', description=f'Alerts turned {response.content} for website {website["index"]}', color=0x00ff00)
    embed.set_footer(text='up!alert')
    await ctx.send(embed=embed)

@client.command()
async def schedule(ctx, index=None, *, schedule=None):
    # If the index argument is not provided, prompt the user for it
    if index is None:
        embed = discord.Embed(title='Index', description='Which monitor do you want to set a schedule for? Please enter the index of the monitor.', color=0x00ff00)
        embed.set_footer(text='up!schedule')
        await ctx.send(embed=embed)
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()
        try:
            response = await client.wait_for('message', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            embed = discord.Embed(title='Error', description='Sorry, you took too long to respond.', color=0xff0000)
            embed.set_footer(text='up!schedule')
            await ctx.send(embed=embed)
            return
        index = response.content

    # If the schedule argument is not provided, prompt the user for it
    if schedule is None:
        embed = discord.Embed(title='Schedule', description='What schedule do you want to set for the monitor? Please enter a cron expression.', color=0x00ff00)
        embed.set_footer(text='up!schedule')
        await ctx.send(embed=embed)
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
        try:
            response = await client.wait_for('message', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            embed = discord.Embed(title='Error', description='Sorry, you took too long to respond.', color=0xff0000)
            embed.set_footer(text='up!schedule')
            await ctx.send(embed=embed)
            return
        schedule = response.content

    # Update the schedules.json file with the new schedule
    with open('schedules.json', 'r') as f:
        schedules = json.load(f)
    user_schedules = schedules.get(str(ctx.author.id), {})
    user_schedules[index] = schedule
    schedules[str(ctx.author.id)] = user_schedules
    with open('schedules.json', 'w') as f:
        json.dump(schedules, f)

    # Send a success message
    await ctx.send(f'Schedule set for monitor {index}')

@client.command()
async def history(ctx, index=None):
    # If the index argument is not provided, prompt the user for it
    if index is None:
        embed = discord.Embed(title='Index', description='Which monitor do you want to view the history for? Please enter the index of the monitor.', color=0x00ff00)
        embed.set_footer(text='up!history')
        await ctx.send(embed=embed)
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()
        try:
            response = await client.wait_for('message', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            embed = discord.Embed(title='Error', description='Sorry, you took too long to respond.', color=0xff0000)
            embed.set_footer(text='up!history')
            await ctx.send(embed=embed)
            return
        index = response.content

    # Load the history.json file and get the history for the specified monitor
    with open('history.json', 'r') as f:
        history = json.load(f)
    user_history = history.get(str(ctx.author.id), {})
    monitor_history = user_history.get(index, [])
    if not monitor_history:
        embed = discord.Embed(title='History', description=f'No history found for monitor {index}', color=0x00ff00)
        embed.set_footer(text='up!history')
        await ctx.send(embed=embed)
        return

    # Format and send the history message in an embed
    history_message = ''
    for entry in monitor_history:
        history_message += f'{entry["time"]}: {entry["status"]}\n'
    embed = discord.Embed(title='History', description=history_message, color=0x00ff00)
    embed.set_footer(text='up!history')
    await ctx.send(embed=embed)

@client.command()
async def analytics(ctx, index=None):
    # If the index argument is not provided, prompt the user for it
    if index is None:
        embed = discord.Embed(title='Index', description='Which monitor do you want to view the analytics for? Please enter the index of the monitor.', color=0x00ff00)
        embed.set_footer(text='up!analytics')
        await ctx.send(embed=embed)
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()
        try:
            response = await client.wait_for('message', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            embed = discord.Embed(title='Error', description='Sorry, you took too long to respond.', color=0xff0000)
            embed.set_footer(text='up!analytics')
            await ctx.send(embed=embed)
            return
        index = response.content

    # Load the analytics.json file and get the analytics for the specified monitor
    with open('analytics.json', 'r') as f:
        analytics = json.load(f)
    user_analytics = analytics.get(str(ctx.author.id), {})
    monitor_analytics = user_analytics.get(index, {})
    if not monitor_analytics:
        embed = discord.Embed(title='Analytics', description=f'No analytics found for monitor {index}', color=0x00ff00)
        embed.set_footer(text='up!analytics')
        await ctx.send(embed=embed)
        return

    # Format and send the analytics message in an embed
    response_times = monitor_analytics.get('average_response_time', [])
    error_rate = monitor_analytics.get('error_rate', 0)
    uptime_percentage = monitor_analytics.get('uptime_percentage', 0)
    analytics_message = f'Average response time: {response_times}ms\nError rate: {error_rate}\nUptime percentage: {uptime_percentage}'
    embed = discord.Embed(title='Analytics', description=analytics_message, color=0x00ff00)
    embed.set_footer(text='up!analytics')
    await ctx.send(embed=embed)


@client.command()
async def monitor(ctx):
    split_message = ctx.message.content.split()
    if len(split_message) < 2:
        embed = discord.Embed(title='Error', description='Please include a website to monitor. Example: up!monitor https://example.com', color=0xff0000)
        embed.set_footer(text='up!monitor')
        await ctx.send(embed=embed)
        return
    website = split_message[1]
    with open('websites.json', 'r') as f:
        websites = json.load(f)
    user_websites = websites.get(str(ctx.author.id), [])
    for user_website in user_websites:
        if user_website['url'] == website:
            embed = discord.Embed(title='Error', description='That website is already being monitored', color=0xff0000)
            embed.set_footer(text='up!monitor')
            await ctx.send(embed=embed)
            return
    embed = discord.Embed(title='Method', description='''Which one? 
1. HEAD
2. GET
3. POST? 
Reply with the 1, 2 or 3.''', color=0x00ff00)
    embed.set_footer(text='up!monitor')
    await ctx.send(embed=embed)
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content in ['1', '2', '3']
    try:
        response = await client.wait_for('message', check=check, timeout=30.0)
    except asyncio.TimeoutError:
        embed = discord.Embed(title='Error', description='Sorry, you took too long to respond.', color=0xff0000)
        embed.set_footer(text='up!monitor')
        await ctx.send(embed=embed)
        return
    method = ''
    if response.content == '1':
        method = 'HEAD'
    elif response.content == '2':
        method = 'GET'
    elif response.content == '3':
        method = 'POST'

    # Ask the user for the time interval
    embed = discord.Embed(title='Time Interval', description='''How often do you want to ping the website? 
Enter a number followed by a unit of time. For example: 
s for seconds
m for minute
h for hour
d for day
w for week
You can also use decimal points to specify fractions of a unit. For example:
0.5m for 30 seconds
6.9h for 6 hours and 54 minutes
The minimum interval is 1 minute.''', color=0x00ff00)
    embed.set_footer(text='up!monitor')
    await ctx.send(embed=embed)

    # Use a regular expression to check the format of the time interval
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and re.match(r'\d+(\.\d+)?[smhdw]$', m.content)
    try:
        response = await client.wait_for('message', check=check, timeout=30.0)
    except asyncio.TimeoutError:
        embed = discord.Embed(title='Error', description='Sorry, you took too long to respond.', color=0xff0000)
        embed.set_footer(text='up!monitor')
        await ctx.send(embed=embed)
        return

    # Convert the time interval to seconds and store it in the websites.json file
    time_interval = response.content
    unit = time_interval[-1]
    factor = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800}
    try:
        number = float(time_interval[:-1])
        seconds = number * factor[unit]
        if seconds < 60:
            raise ValueError('Minimum time interval is 1 minute. Please try again')
    except ValueError as e:
        embed = discord.Embed(title='Error', description=f'{e}', color=0xff0000)
        embed.set_footer(text='up!monitor')
        await ctx.send(embed=embed)
        return

    # Generate a new index for the website by finding the maximum index of existing websites and adding 1
    max_index = max((int(user_website['index']) for user_website in user_websites), default=0)
    new_index = str(max_index + 1)
    user_websites.append({'url': website, 'method': method, 'time_interval': seconds, 'index': new_index})
    websites[str(ctx.author.id)] = user_websites
    with open('websites.json', 'w') as f:
        json.dump(websites, f)

    # Delete the user's messages if possible
    try:
        await ctx.message.delete()
        await response.delete()
    except discord.Forbidden:
        pass

    # Send a success message
    embed = discord.Embed(title='Success', description='Website added', color=0x00ff00)
    embed.set_footer(text='up!monitor')
    await ctx.send(embed=embed)


@client.command()
async def remove(ctx):
    split_message = ctx.message.content.split()
    if len(split_message) < 2:
        embed = discord.Embed(title='Error', description='Please include an index to remove. Example: up!remove 1\nIf you do not know the index, use the up!stats command to view your monitored websites.', color=0xff0000)
        embed.set_footer(text='up!remove')
        await ctx.send(embed=embed)
        return
    argument = split_message[1]
    with open('websites.json', 'r') as f:
        websites = json.load(f)
    user_websites = websites.get(str(ctx.author.id), [])

    # Check if the argument is an index
    if argument.isdigit():
        index = int(argument)
        if index < 1 or index > len(user_websites):
            embed = discord.Embed(title='Error', description=f'Invalid index. Please enter a number between 1 and {len(user_websites)}\nIf you do not know the index, use the up!stats command to view your monitored websites.', color=0xff0000)
            embed.set_footer(text='up!remove')
            await ctx.send(embed=embed)
            return
        del user_websites[index - 1]

        # Update the file and send a success message
        websites[str(ctx.author.id)] = user_websites
        with open('websites.json', 'w') as f:
            json.dump(websites, f)
        if not isinstance(ctx.channel, discord.channel.DMChannel):
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
        embed = discord.Embed(title='Success', description='Website removed', color=0x00ff00)
        embed.set_footer(text='up!remove')
        await ctx.send(embed=embed)

    # If the argument is not an index, send an error message
    else:
        embed = discord.Embed(title='Error', description=f'Invalid argument. Please enter an index to remove. Example: up!remove 1\nIf you do not know the index, use the up!stats command to view your monitored websites.', color=0xff0000)
        embed.set_footer(text='up!remove')
        await ctx.send(embed=embed)

@client.command()
async def stats(ctx):
    with open('websites.json', 'r') as f:
        websites = json.load(f)
    user_websites = websites.get(str(ctx.author.id), [])
    if not user_websites:
        embed = discord.Embed(title='Error', description='You have not added any websites to monitor', color=0xff0000)
        embed.set_footer(text='up!stats')
        await ctx.send(embed=embed)
        return
    stats_message = ''
    count = 1
    for website in user_websites:
        url = website['url']
        method = website['method']
        last_ping_time = website.get('last_ping_time', 'N/A')
        response_status = website.get('response_status', 'N/A')
        stats_message += f'{count}. {url}, {method}, last pinged on {last_ping_time} (IST), response status: {response_status}\n'
        count += 1
    embed = discord.Embed(title='Stats', description=stats_message, color=0x00ff00)
    embed.set_footer(text='up!stats')
    await ctx.author.send(embed=embed)
    if not isinstance(ctx.channel, discord.channel.DMChannel):
        await ctx.send(f'{ctx.author.mention} Check your DMs!')


client.run("YOUR-TOKEN")
