package main

import (
	"errors"
	"flag"
	"fmt"
	"net/http"
	"os"
	"time"
)

type hostname struct {
	name      string
	signature string
	time      time.Time
}

type hostdata struct {
	timestamp time.Time
	hostnames []hostname
}

func main() {
	port := flag.Int("port", 7331, "port to listen on")
	flag.Parse()

	http.HandleFunc("/", getData)

	listenHost := fmt.Sprintf(":%d", *port)

	err := http.ListenAndServe(listenHost, nil)
	if errors.Is(err, http.ErrServerClosed) {
		fmt.Printf("server closed\n")
	} else if err != nil {
		fmt.Printf("error starting server: %s\n", err)
		os.Exit(1)
	}
}

func getData(w http.ResponseWriter, r *http.Request) {
	fmt.Fprintf(w, "Hello, %s!", r.URL.Path[1:])
}
