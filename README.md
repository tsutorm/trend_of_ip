# trend_of_ip


## run script

```
$ python trend_of_ip.py [logfile]
```

or

```
$ cat [logfile] | python trend_of_ip.py
```

## run docker

```
$ docker run --rm -v `pwd`:/app -t tsutorm/trend_of_ip [logfile]
```

or

```
$ cat [logfile] | docker run --rm -i tsutorm/trend_of_ip
```
